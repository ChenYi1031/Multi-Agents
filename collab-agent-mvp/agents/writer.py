"""
报告撰写员 Agent 节点
基于搜索结果，生成结构化的 Markdown 格式研究报告
"""

from __future__ import annotations

import json
import logging

from langchain_openai import ChatOpenAI

from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL_NAME

logger = logging.getLogger(__name__)


def _build_llm(**kwargs):
    """构建 ChatOpenAI 实例，自动注入通用配置"""
    return ChatOpenAI(
        model=OPENAI_MODEL_NAME,
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        **kwargs,
    )


def writer_node(state: dict) -> dict:
    """
    撰写员节点：基于搜索结果生成 Markdown 报告

    Args:
        state: ResearchState 字典，包含 topic, search_results, error 字段

    Returns:
        dict: 包含 draft_report 和 final_report 字段的更新
    """
    topic = state.get("topic", "")
    results = state.get("search_results", [])

    # 如果有错误且无搜索结果，直接返回错误
    if state.get("error") and not results:
        return {
            "draft_report": "",
            "final_report": "",
            "error": state["error"],
        }

    # 序列化搜索结果
    research_text = json.dumps(results, indent=2, ensure_ascii=False)

    # 如果搜索结果为空，给出提示
    if not results:
        research_text = "未找到相关搜索结果，请基于你的知识生成报告。"

    prompt = f"""你是一位资深报告撰写员。你会收到一份关于"{topic}"的搜索结果列表。
请基于这些信息，撰写一份专业的 Markdown 格式报告。

报告结构要求：
1. 标题（一级标题）
2. 摘要（一段话概括）
3. 主要发现（二级标题，每个发现一个小节，引用来源）
4. 结论与展望（一段话）

要求：
- 必须引用所有给定的来源，使用 [来源名称](URL) 格式。
- 语言专业、客观，避免夸张。
- 输出纯净的 Markdown，不要包含解释性文字。

以下是搜索结果：
{research_text}
"""

    # 初始化 LLM，temperature 设中等以保证写作质量
    llm = _build_llm(temperature=0.7)

    try:
        response = llm.invoke(prompt)
        draft = response.content
        return {"draft_report": draft, "final_report": draft}
    except Exception as e:
        logger.error(f"报告生成失败: {e}")
        error_msg = f"报告生成失败: {e}"
        return {
            "draft_report": f"# 报告生成出错\n\n{error_msg}",
            "final_report": f"# 报告生成出错\n\n{error_msg}",
            "error": error_msg,
        }
