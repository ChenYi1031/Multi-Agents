"""
搜索工具封装
支持 DuckDuckGo (v6 SDK) 免费搜索和 Tavily Search API 两种后端
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import List, Optional

logger = logging.getLogger(__name__)


def _get_proxy() -> Optional[str]:
    """从环境变量获取代理 URL"""
    return os.getenv("HTTP_PROXY") or os.getenv("http_proxy") or \
           os.getenv("HTTPS_PROXY") or os.getenv("https_proxy") or None


def _search_duckduckgo(query: str, max_results: int = 5) -> List[dict]:
    """使用 DuckDuckGo v6 SDK 搜索
    自动尝试：已配置 proxy → 失败后尝试无 proxy → 反过来也试一次
    """
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        logger.error("duckduckgo_search 未安装")
        return []

    # 收集待尝试的 proxy 选项（去重）
    configured_proxy = _get_proxy()
    proxy_options = []
    if configured_proxy:
        proxy_options.append(configured_proxy)
    proxy_options.append(None)  # 总是试一次无代理
    # 如果配置的 proxy 和无代理不同，两个都会试
    # 如果相同（即未配置），只试一次 None
    if len(proxy_options) > 1 and configured_proxy is None:
        proxy_options = [None]

    last_error = ""
    for proxy in proxy_options:
        results = []
        proxy_label = proxy if proxy else "直接连接"
        try:
            with DDGS(proxy=proxy, timeout=3) as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    results.append({
                        "title": r.get("title", ""),
                        "summary": r.get("body", "") or r.get("snippet", ""),
                        "source": r.get("href", "") or "",
                    })
            if results:
                logger.info(f"DuckDuckGo 返回 {len(results)} 条结果 ({proxy_label})")
                return results
        except Exception as e:
            last_error = str(e)
            logger.warning(f"DuckDuckGo {proxy_label} 搜索失败: {e}")
            continue

    logger.warning(f"DuckDuckGo 全部方式失败: {last_error}")
    return []


def _tavily_available() -> bool:
    """检查 Tavily 是否可用（已安装且有 API key）"""
    try:
        from config import TAVILY_API_KEY
        if TAVILY_API_KEY:
            return True
    except (ImportError, Exception):
        pass
    # 也检查环境变量
    return bool(os.getenv("TAVILY_API_KEY"))


def _search_tavily(query: str, max_results: int = 5) -> List[dict]:
    """使用 Tavily Search API 搜索"""
    if not _tavily_available():
        logger.info("Tavily 不可用（无 API Key），跳过")
        return []

    try:
        from langchain_community.tools import TavilySearchResults
    except ImportError:
        logger.error("Tavily 未安装")
        return []

    tool = TavilySearchResults(max_results=max_results)
    try:
        raw = tool.invoke({"query": query})
        results = []
        for item in raw:
            results.append({
                "title": item.get("title", ""),
                "summary": item.get("content", ""),
                "source": item.get("url", ""),
            })
        logger.info(f"Tavily 返回 {len(results)} 条结果")
        return results
    except Exception as e:
        logger.warning(f"Tavily 搜索失败: {e}")
        return []


def deduplicate_results(results: List[dict]) -> List[dict]:
    """
    按 source URL 去重，保留首次出现的条目。
    无 source 的条目按 title 去重；两者皆无则保留。
    """
    seen_sources: set = set()
    seen_titles: set = set()
    deduped: List[dict] = []
    for r in results:
        src_raw = r.get("source")
        src = str(src_raw).strip() if src_raw is not None else ""
        title_raw = r.get("title")
        title = str(title_raw).strip() if title_raw is not None else ""
        if src and src in seen_sources:
            continue
        if not src and title and title in seen_titles:
            continue
        if src:
            seen_sources.add(src)
        if title:
            seen_titles.add(title)
        deduped.append(r)
    return deduped


def search(query: str) -> List[dict]:
    """
    搜索并返回结构化结果列表

    Args:
        query: 搜索关键词

    Returns:
        List[dict]: 每个元素包含 title, summary, source 三个字段
        搜索失败时返回空列表（不会抛异常）
    """
    from config import USE_DUCKDUCKGO

    results = []
    if USE_DUCKDUCKGO:
        results = _search_duckduckgo(query)
        if not results:
            logger.info("DuckDuckGo 无结果，尝试 Tavily 兜底")
            results = _search_tavily(query)
    else:
        results = _search_tavily(query)
        if not results:
            logger.info("Tavily 无结果，尝试 DuckDuckGo 兜底")
            results = _search_duckduckgo(query)

    return results
