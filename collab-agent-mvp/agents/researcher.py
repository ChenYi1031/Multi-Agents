"""
搜索研究员 Agent 节点
根据用户主题，使用 LLM + 搜索工具收集信息，返回结构化 JSON 结果
"""

from __future__ import annotations

import json
import logging
import re
from typing import List

from langchain.schema import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL_NAME
from tools.search import search

logger = logging.getLogger(__name__)


RESEARCHER_PROMPT = """你是一位专业的研究助理。你的任务是根据用户提供的主题，列出 3-5 个最重要的信息点或事实。
对于每个信息点，请使用搜索工具查找可靠的来源，并以 JSON 格式返回结果。

要求：
- 每个信息点必须包含: title (简短标题), summary (2-3 句话的摘要), source (URL)。
- 优先使用近期、权威的来源。
- 输出格式必须是严格的 JSON 数组，不要包含任何其他文字。

示例输出：
[
  {{"title": "气候变化对农业的影响", "summary": "...", "source": "https://..."}},
  ...
]"""


def _parse_json_from_response(content: str) -> List[dict]:
    """
    从 LLM 响应中解析 JSON 数组
    处理 ```json ... ``` 代码块和纯 JSON 两种情况
    """
    # 尝试提取 markdown 代码块中的 JSON
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_str = content.strip()

    # 尝试解析
    results = json.loads(json_str)

    # 确保是列表
    if isinstance(results, list):
        return results
    elif isinstance(results, dict):
        return [results]
    else:
        raise ValueError(f"JSON 格式不正确: 期望列表或字典，得到 {type(results)}")


def researcher_node(state: dict) -> dict:
    """
    研究员节点：分析主题 → 搜索信息 → 返回结构化结果

    Args:
        state: ResearchState 字典，包含 topic 字段

    Returns:
        dict: 包含 search_results 字段的更新
    """
    topic = state.get("topic", "")
    if not topic:
        return {"search_results": [], "error": "研究主题为空"}

    # 初始化 LLM，temperature 设低以保证事实性
    llm = ChatOpenAI(
        model=OPENAI_MODEL_NAME,
        api_key=OPENAI_API_KEY,
        temperature=0.3,
    )

    # 将搜索函数包装为 LangChain 工具
    from langchain.tools import tool

    @tool
    def search_tool(query: str) -> str:
        """搜索网络获取最新信息"""
        results = search(query)
        return json.dumps(results, ensure_ascii=False, indent=2)

    llm_with_tools = llm.bind_tools([search_tool])

    messages = [
        SystemMessage(content=RESEARCHER_PROMPT),
        HumanMessage(content=f"研究主题：{topic}"),
    ]

    # 第一次尝试
    try:
        response = llm_with_tools.invoke(messages)
        search_results = _parse_json_from_response(response.content)
        return {"search_results": search_results}
    except Exception as e:
        logger.warning(f"第一次 JSON 解析失败，重试: {e}")

    # 重试一次
    try:
        messages.append(SystemMessage(
            content="请确保输出严格的 JSON 数组格式，不要包含额外的文字说明。"
        ))
        response = llm_with_tools.invoke(messages)
        search_results = _parse_json_from_response(response.content)
        return {"search_results": search_results}
    except Exception as e:
        logger.error(f"JSON 解析重试仍失败: {e}")
        return {"search_results": [], "error": f"搜索信息解析失败: {e}"}
