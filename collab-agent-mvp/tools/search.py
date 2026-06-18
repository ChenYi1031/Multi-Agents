"""
搜索工具封装
支持 Tavily Search API 和 DuckDuckGo 免费搜索两种后端
"""

from __future__ import annotations

import json
import logging
from typing import List

logger = logging.getLogger(__name__)


def _search_tavily(query: str, max_results: int = 5) -> List[dict]:
    """使用 Tavily Search API 进行搜索"""
    from langchain_community.tools import TavilySearchResults

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
        return results
    except Exception as e:
        logger.error(f"Tavily 搜索失败: {e}")
        return []


def _search_duckduckgo(query: str, max_results: int = 5) -> List[dict]:
    """使用 DuckDuckGo 免费搜索"""
    from langchain_community.tools import DuckDuckGoSearchResults
    from langchain_community.utilities import DuckDuckGoSearchAPIWrapper

    wrapper = DuckDuckGoSearchAPIWrapper(max_results=max_results)
    tool = DuckDuckGoSearchResults(api_wrapper=wrapper)
    try:
        raw = tool.invoke({"query": query})
        # DuckDuckGo 返回的可能是字符串，需要解析
        results = []
        if isinstance(raw, str):
            # 尝试按分隔符解析
            import re
            snippets = re.split(r'\n\d+\.\s*', raw)
            for snippet in snippets:
                if not snippet.strip():
                    continue
                # 提取标题和摘要
                lines = snippet.strip().split('\n')
                title = lines[0] if lines else ""
                summary = '\n'.join(lines[1:]) if len(lines) > 1 else ""
                results.append({
                    "title": title.strip()[:100],
                    "summary": summary.strip()[:300],
                    "source": "",
                })
        elif isinstance(raw, list):
            for item in raw:
                results.append({
                    "title": item.get("title", ""),
                    "summary": item.get("snippet", "") or item.get("body", ""),
                    "source": item.get("link", "") or item.get("href", ""),
                })
        return results[:max_results]
    except Exception as e:
        logger.error(f"DuckDuckGo 搜索失败: {e}")
        return []


def search(query: str) -> List[dict]:
    """
    搜索并返回结构化结果列表

    Args:
        query: 搜索关键词

    Returns:
        List[dict]: 每个元素包含 title, summary, source 三个字段
    """
    from config import USE_DUCKDUCKGO

    if USE_DUCKDUCKGO:
        return _search_duckduckgo(query)
    else:
        return _search_tavily(query)
