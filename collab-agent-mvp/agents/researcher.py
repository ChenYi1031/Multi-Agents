"""
搜索研究员 Agent 节点
根据用户主题，使用 LLM + 搜索工具收集信息，返回结构化 JSON 结果
正确处理 LLM 工具调用（function calling）循环
"""

from __future__ import annotations

import json
import logging
import re
from typing import List

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain.tools import tool
from langchain_openai import ChatOpenAI

from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL_NAME
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
  {"title": "标题示例", "summary": "摘要内容示例", "source": "https://example.com"},
  {"title": "标题示例", "summary": "摘要内容示例", "source": "https://example.org"}
]"""


def _parse_json_from_response(content: str) -> List[dict]:
    """从 LLM 响应中解析 JSON 数组，处理 ```json``` 代码块和纯 JSON"""
    if not content or not content.strip():
        raise ValueError("响应内容为空")

    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
    json_str = json_match.group(1) if json_match else content.strip()

    results = json.loads(json_str)
    if isinstance(results, list):
        return results
    elif isinstance(results, dict):
        return [results]
    raise ValueError(f"JSON 格式不正确: 期望列表或字典，得到 {type(results)}")


def _build_llm(**kwargs):
    """构建 ChatOpenAI 实例，自动注入通用配置"""
    return ChatOpenAI(
        model=OPENAI_MODEL_NAME,
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        **kwargs,
    )


def _run_tool_loop(llm_with_tools, messages: list) -> AIMessage:
    """
    执行工具调用循环：
    1. 调用 LLM
    2. 如果有 tool_calls，逐个执行并注入结果
    3. 重复直到 LLM 返回纯文本内容
    """
    for attempt in range(5):  # 防止无限循环
        response: AIMessage = llm_with_tools.invoke(messages)

        logger.debug(f"[attempt {attempt}] response type: {type(response).__name__}")
        logger.debug(f"[attempt {attempt}] content: {response.content[:200] if response.content else '(empty)'}")
        logger.debug(f"[attempt {attempt}] tool_calls: {getattr(response, 'tool_calls', None)}")

        # 检查是否有 tool calls
        if not hasattr(response, "tool_calls") or not response.tool_calls:
            return response  # 纯文本响应，退出循环

        # 执行所有 tool calls
        messages.append(response)
        for tc in response.tool_calls:
            # 兼容不同版本的 LangChain
            if isinstance(tc, dict):
                tool_name = tc.get("name", tc.get("function", {}).get("name", ""))
                tool_args = tc.get("args", tc.get("function", {}).get("arguments", {}))
                tool_call_id = tc.get("id", tc.get("function", {}).get("call_id", ""))
            else:
                tool_name = getattr(tc, "name", "")
                tool_args = getattr(tc, "args", {})
                tool_call_id = getattr(tc, "id", "")

            if tool_name == "search_tool":
                query = tool_args.get("query", "")
                logger.info(f"执行搜索工具: {query}")
                result = search(query)
                result_str = json.dumps(result, ensure_ascii=False, indent=2)
                messages.append(ToolMessage(content=result_str, tool_call_id=tool_call_id))
            else:
                logger.warning(f"未知工具调用: {tool_name}")
                messages.append(ToolMessage(
                    content=json.dumps({"error": f"未知工具: {tool_name}"}),
                    tool_call_id=tool_call_id,
                ))

    # 超限后返回最后一次响应
    logger.warning("工具调用循环达到最大次数")
    return response


def researcher_node(state: dict) -> dict:
    """
    研究员节点：分析主题 → 搜索信息 → 返回结构化结果
    正确处理 LLM function calling 循环
    """
    topic = state.get("topic", "")
    if not topic:
        return {"search_results": [], "error": "研究主题为空"}

    llm = _build_llm(temperature=0.3)

    @tool
    def search_tool(query: str) -> str:
        """搜索网络获取最新信息。输入为搜索关键词，返回结构化结果列表。"""
        results = search(query)
        return json.dumps(results, ensure_ascii=False, indent=2)

    llm_with_tools = llm.bind_tools([search_tool])

    # ── 首次尝试 ──
    try:
        messages = [
            SystemMessage(content=RESEARCHER_PROMPT),
            HumanMessage(content=f"研究主题：{topic}"),
        ]
        response = _run_tool_loop(llm_with_tools, messages)
        search_results = _parse_json_from_response(response.content)
        return {"search_results": search_results}
    except Exception as e:
        logger.warning(f"第一次 JSON 解析失败，重试: {e}")

    # ── 重试（附加严格提示） ──
    try:
        messages = [
            SystemMessage(content=RESEARCHER_PROMPT),
            HumanMessage(content=f"研究主题：{topic}"),
            SystemMessage(content="请确保输出严格的 JSON 数组格式，不要包含额外的文字说明。"),
        ]
        response = _run_tool_loop(llm_with_tools, messages)
        search_results = _parse_json_from_response(response.content)
        return {"search_results": search_results}
    except Exception as e:
        logger.error(f"JSON 解析重试仍失败: {e}")

        # ── 兜底：直接用搜索工具搜，跳过 LLM JSON 解析 ──
        logger.info("使用直接搜索作为兜底方案")
        try:
            raw_results = search(topic)
            if raw_results:
                return {"search_results": raw_results}
        except Exception as e2:
            logger.error(f"兜底搜索也失败: {e2}")

        # 搜索失败：返回空列表，但不设 error
        # writer 节点会基于 LLM 自身知识生成报告
        logger.warning("所有搜索方式均失败，返回空结果（writer 将基于 LLM 知识生成）")
        return {"search_results": []}
