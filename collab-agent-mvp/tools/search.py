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
    """使用 DuckDuckGo v6 SDK 搜索"""
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        logger.error("duckduckgo_search 未安装")
        return []

    proxy = _get_proxy()
    results = []

    # 遇到限速时最多重试 25 次，每次间隔递增
    for attempt in range(25):
        try:
            with DDGS(proxy=proxy, timeout=10) as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    results.append({
                        "title": r.get("title", ""),
                        "summary": r.get("body", "") or r.get("snippet", ""),
                        "source": r.get("href", "") or "",
                    })
            if results:
                logger.info(f"DuckDuckGo 返回 {len(results)} 条结果 (尝试 {attempt+1})")
                return results
        except Exception as e:
            err_str = str(e)
            if "Ratelimit" in err_str:
                wait = min(attempt + 2, 10)  # 等待时间递增，最长 10s
                logger.warning(f"DuckDuckGo 限速 (第{attempt+1}/25次)，{wait}s 后重试...")
                time.sleep(wait)
                continue
            logger.warning(f"DuckDuckGo 搜索失败: {e}")
            return []

    logger.error(f"DuckDuckGo 限速重试 25 次均失败")
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
