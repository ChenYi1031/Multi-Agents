"""
搜索研究员 Agent 节点
根据用户主题，使用 LLM + 搜索工具收集信息，返回结构化 JSON 结果
正确处理 LLM 工具调用（function calling）循环
支持异步执行
"""

from __future__ import annotations

import json
import logging
import re
from typing import List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain.tools import tool
from langchain_openai import ChatOpenAI

from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL_NAME
from tools.search import deduplicate_results, search

logger = logging.getLogger(__name__)


RESEARCHER_PROMPT = """你是一位专业的研究助理。你的任务是根据用户提供的主题，列出 3-5 个最重要的信息点或事实。
对于每个信息点，请使用搜索工具查找可靠的来源，并以 JSON 格式返回结果。

要求：
- 每个信息点必须包含: title (简短标题), summary (2-3 句话的摘要), source (URL)。
- 优先使用近期、权威的来源。
- 输出格式必须是严格的 JSON 数组，不要包含任何其他文字。
- 不要使用 {{ 或 }}，使用单大括号。

示例输出：
[
  {"title": "标题示例", "summary": "摘要内容示例", "source": "https://example.com"},
  {"title": "标题示例", "summary": "摘要内容示例", "source": "https://example.org"}
]"""


def _extract_json_array(text: str) -> Optional[str]:
    """
    从文本中提取 JSON 数组字符串。
    优先级：```json 代码块 > [...] 包裹 > 全文
    """
    if not text or not text.strip():
        return None

    # 1. ```json [...] ``` 或 ``` [...] ```
    block = re.search(r'```(?:json)?\s*(\[\s*[\s\S]*?\s*\])\s*```', text)
    if block:
        return block.group(1)

    # 2. 直接找 [...] 包裹的最外层数组
    #    从第一个 [ 匹配到最后一个 ]
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end > start:
        candidate = text[start:end + 1]
        # 粗略校验：内容是 JSON 可解析的
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass

    # 3. 全文尝试解析
    return text.strip()


def _clean_json_string(s: str) -> str:
    """清理常见 JSON 格式问题"""
    # 去除尾部逗号 (Python json 不支持 trailing comma)
    s = re.sub(r',\s*([\]}])', r'\1', s)
    # 单引号 → 双引号
    s = re.sub(r"(?<!\\)'", '"', s)
    # True/False/None → true/false/null
    s = re.sub(r'\bTrue\b', 'true', s)
    s = re.sub(r'\bFalse\b', 'false', s)
    s = re.sub(r'\bNone\b', 'null', s)
    return s


def _parse_json_from_response(content: str) -> List[dict]:
    """
    从 LLM 响应中解析 JSON 数组，多级降级。
    
    降级链：```json 代码块 > [...] 外层包裹 > 全文 JSON
    > 清洗后重试 > 提取任意 {...} 包裹
    """
    if not content or not content.strip():
        raise ValueError("响应内容为空")

    extracted = _extract_json_array(content)

    # 尝试直接解析
    for attempt in range(2):
        try:
            results = json.loads(extracted)
            if isinstance(results, list):
                return results
            elif isinstance(results, dict):
                return [results]
            raise ValueError(f"JSON 格式不正确: 期望列表或字典，得到 {type(results)}")
        except json.JSONDecodeError:
            if attempt == 0:
                # 第一次失败 → 清洗后重试
                extracted = _clean_json_string(extracted)
                continue
            # 第二次还失败 → 尝试提取所有 {...} 对象
            logger.warning("JSON 解析失败，尝试提取对象片段")
            objects = re.findall(r'\{[^{}]*\}', extracted)
            results = []
            for obj_str in objects:
                try:
                    obj_str = _clean_json_string(obj_str)
                    parsed = json.loads(obj_str)
                    if isinstance(parsed, dict):
                        results.append(parsed)
                except json.JSONDecodeError:
                    continue
            if results:
                return results
            raise ValueError(f"无法从响应中提取 JSON: {content[:300]}")


def _build_llm(**kwargs):
    """构建 ChatOpenAI 实例，自动注入通用配置"""
    return ChatOpenAI(
        model=OPENAI_MODEL_NAME,
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        **kwargs,
    )


def _run_tool_loop(llm: ChatOpenAI, llm_with_tools, messages: list) -> AIMessage:
    """
    执行工具调用循环：
    1. 调用 LLM（带工具）
    2. 如果有 tool_calls，逐个执行并注入结果
    3. 重复直到 LLM 返回纯文本内容
    4. 5 轮超限后，用不带工具的 LLM 强制输出 JSON
    """
    for attempt in range(5):  # 防止无限循环
        response: AIMessage = llm_with_tools.invoke(messages)

        logger.debug(f"[attempt {attempt}] response type: {type(response).__name__}")
        logger.debug(f"[attempt {attempt}] content: {response.content[:200] if response.content else '(empty)'}")
        logger.debug(f"[attempt {attempt}] tool_calls: {getattr(response, 'tool_calls', None)}")

        # 检查是否有 tool calls
        if not hasattr(response, "tool_calls") or not response.tool_calls:
            logger.info(f"工具调用循环在 {attempt+1} 轮完成")
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

    # ── 超限兜底：用不带工具的 LLM 强制输出 JSON ──
    logger.warning("工具调用循环达到最大次数，强制 LLM 输出 JSON")
    messages.append(SystemMessage(
        content="你已用完工具调用次数。请基于已有信息，直接输出 JSON 数组结果，不要调用任何工具。"
    ))
    final_response: AIMessage = llm.invoke(messages)
    return final_response


async def _run_tool_loop_async(llm: ChatOpenAI, llm_with_tools, messages: list) -> AIMessage:
    """
    异步工具调用循环：
    1. 调用 LLM（带工具）
    2. 如果有 tool_calls，逐个执行并注入结果
    3. 重复直到 LLM 返回纯文本内容
    4. 5 轮超限后，用不带工具的 LLM 强制输出 JSON
    """
    for attempt in range(5):
        response: AIMessage = await llm_with_tools.ainvoke(messages)

        logger.debug(f"[async attempt {attempt}] response type: {type(response).__name__}")
        logger.debug(f"[async attempt {attempt}] content: {response.content[:200] if response.content else '(empty)'}")
        logger.debug(f"[async attempt {attempt}] tool_calls: {getattr(response, 'tool_calls', None)}")

        if not hasattr(response, "tool_calls") or not response.tool_calls:
            logger.info(f"异步工具调用循环在 {attempt+1} 轮完成")
            return response

        messages.append(response)
        for tc in response.tool_calls:
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
                logger.info(f"执行搜索工具 (async): {query}")
                result = search(query)
                result_str = json.dumps(result, ensure_ascii=False, indent=2)
                messages.append(ToolMessage(content=result_str, tool_call_id=tool_call_id))
            else:
                logger.warning(f"未知工具调用: {tool_name}")
                messages.append(ToolMessage(
                    content=json.dumps({"error": f"未知工具: {tool_name}"}),
                    tool_call_id=tool_call_id,
                ))

    logger.warning("异步工具调用循环达到最大次数，强制 LLM 输出 JSON")
    messages.append(SystemMessage(
        content="你已用完工具调用次数。请基于已有信息，直接输出 JSON 数组结果，不要调用任何工具。"
    ))
    final_response: AIMessage = await llm.ainvoke(messages)
    return final_response


async def researcher_node(state: dict) -> dict:
    """
    异步研究员节点：分析主题 → 搜索信息 → 返回结构化结果
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
        response = await _run_tool_loop_async(llm, llm_with_tools, messages)
        search_results = _parse_json_from_response(response.content)
        return {"search_results": deduplicate_results(search_results)}
    except Exception as e:
        logger.warning(f"第一次 JSON 解析失败，重试: {e}")

    # ── 重试（附加严格提示） ──
    try:
        messages = [
            SystemMessage(content=RESEARCHER_PROMPT),
            HumanMessage(content=f"研究主题：{topic}"),
            SystemMessage(content="请确保输出严格的 JSON 数组格式，不要包含额外的文字说明。"),
        ]
        response = await _run_tool_loop_async(llm, llm_with_tools, messages)
        search_results = _parse_json_from_response(response.content)
        return {"search_results": deduplicate_results(search_results)}
    except Exception as e:
        logger.error(f"JSON 解析重试仍失败: {e}")

        # ── 兜底：直接用搜索工具搜，跳过 LLM JSON 解析 ──
        logger.info("使用直接搜索作为兜底方案")
        try:
            raw_results = search(topic)
            if raw_results:
                return {"search_results": deduplicate_results(raw_results)}
        except Exception as e2:
            logger.error(f"兜底搜索也失败: {e2}")

        logger.warning("所有搜索方式均失败，返回空结果（writer 将基于 LLM 知识生成）")
        return {"search_results": []}



