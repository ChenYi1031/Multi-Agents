"""
报告撰写员 Agent 节点
基于搜索结果，生成结构化的 Markdown 格式研究报告
含质量校验 + 自动修复机制 + 截断检测续写
支持异步执行
"""

from __future__ import annotations

import json
import logging
import re
from typing import List

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


# ──────────────────────────────────────────────
# 报告质量校验
# ──────────────────────────────────────────────

REQUIRED_SECTIONS = ["摘要", "结论", "展望"]


def validate_report(report: str, topic: str, results: List[dict]) -> List[str]:
    """
    校验 Markdown 报告质量，返回问题列表。空列表 = 合格。

    检查项：
    1. 非空
    2. 不含报错标记
    3. 有标题（# 或 ##）
    4. 标题后有内容
    5. 有预期关键词（摘要/结论/展望）
    6. 有搜索结果时至少引用一个来源
    """
    issues: List[str] = []

    if not report or not report.strip():
        return ["报告内容为空"]

    # 2. 报错标记
    if "生成出错" in report or "报告生成出错" in report:
        issues.append("报告包含错误标记")

    # 3. 标题
    has_heading = bool(re.search(r'^#{1,2}\s+\S', report, re.MULTILINE))
    if not has_heading:
        issues.append("缺少一级或二级标题")

    # 4. 标题后内容
    sections = re.split(r'^#{1,2}\s+.*$', report, flags=re.MULTILINE)
    empty_sections = [s for s in sections if s.strip() and len(s.strip()) < 10]
    if empty_sections:
        issues.append(f"存在 {len(empty_sections)} 个标题后内容过段")

    # 5. 关键词覆盖
    text_lower = report.lower()
    found = any(kw in text_lower for kw in ["摘要", "结论", "展望", "总结"])
    if not found:
        issues.append("缺少摘要/结论/展望等必需章节")

    # 6. 来源引用
    if results:
        urls_in_report = re.findall(r'https?://[^\s)\]>]+', report)
        source_urls = set(
            r.get("source", "") for r in results if r.get("source")
        )
        if source_urls and not any(u in report for u in source_urls):
            issues.append("未引用任何搜索结果中的来源 URL")

    return issues


def _build_prompt(topic: str, research_text: str, fix_instruction: str = "") -> str:
    """构造报告撰写 prompt，可附加修复指令"""
    fix_section = f"\n\n{fix_instruction}" if fix_instruction else ""
    return f"""你是一位资深报告撰写员。你会收到一份关于"{topic}"的搜索结果列表。
请基于这些信息，撰写一份专业的 Markdown 格式报告。

报告结构要求：
1. 标题（一级标题）
2. 摘要（一段话概括）
3. 主要发现（二级标题，每个发现一个小节，引用来源）
4. 结论与展望（一段话）

要求：
- 必须引用所有给定的来源，使用 [来源名称](URL) 格式。
- 语言专业、客观，避免夸张。
- 输出纯净的 Markdown，不要包含解释性文字。{fix_section}

以下是搜索结果：
{research_text}
"""


def _generate_report(llm, prompt: str) -> str:
    """调用 LLM 生成报告，返回内容 (同步)"""
    response = llm.invoke(prompt)
    return response.content


async def _generate_report_async(llm, prompt: str) -> str:
    """调用 LLM 生成报告，返回内容 (异步)"""
    response = await llm.ainvoke(prompt)
    return response.content


# ──────────────────────────────────────────────
# 截断检测与续写
# ──────────────────────────────────────────────

END_SECTION_KEYWORDS = ["结论", "展望", "总结", "结语", "未来展望"]


def _is_truncated(report: str) -> bool:
    """
    启发式检测报告是否被 token 限制截断。
    返回 True 表示可能不完整。
    """
    if not report or not report.strip():
        return False

    lines = report.strip().splitlines()

    # 1. 最后一行是标题（说明开了一个新节但没内容）
    last_line = lines[-1].strip()
    if re.match(r'^#{1,3}\s+\S', last_line):
        return True

    # 2. 结尾没有空行，且最后一句不是完整结束
    #    (以句号/感叹号/问号结束，或者是 Markdown 分隔符)
    if not re.search(r'[。！？\n#>\-\*]$', last_line):
        # 最后一行太短，不像完整的段落结尾
        if len(last_line) < 30:
            return True

    # 3. 没有包含任何结束章节关键词
    text_last_300 = report[-300:] if len(report) > 300 else report
    has_end_section = any(kw in text_last_300 for kw in END_SECTION_KEYWORDS)
    if not has_end_section:
        return True

    return False


def _continue_report(llm, report: str, topic: str, results_text: str) -> str:
    """
    续写被截断的报告 (同步)。
    """
    prompt = f"""你是一位资深报告撰写员。以下是一份关于"{topic}"的报告，但被截断了。
请从断点处**继续往下写**，不要重复已有内容，直接续写缺失的部分。

已有报告内容：
{report}

--- 请从这里继续写 ---

要求：
- 直接从断点处续写，不要重复标题或已有内容。
- 保持原有的 Markdown 格式和语言风格。
- 如有搜索源，请继续引用 [来源名称](URL)。
- 务必包含结论或展望章节作为结尾。
"""
    try:
        response = llm.invoke(prompt)
        continuation = response.content.strip()
        anchor = report[-50:].strip()
        if anchor and anchor in continuation:
            idx = continuation.index(anchor) + len(anchor)
            continuation = continuation[idx:].strip()
        combined = report.rstrip() + "\n\n" + continuation
        logger.info(f"报告续写完成，原长度={len(report)}，续写后={len(combined)}")
        return combined
    except Exception as e:
        logger.warning(f"报告续写失败: {e}")
        return report


async def _continue_report_async(llm, report: str, topic: str, results_text: str) -> str:
    """
    续写被截断的报告 (异步)。
    将已有报告发给 LLM，要求从断点继续。
    """
    prompt = f"""你是一位资深报告撰写员。以下是一份关于"{topic}"的报告，但被截断了。
请从断点处**继续往下写**，不要重复已有内容，直接续写缺失的部分。

已有报告内容：
{report}

--- 请从这里继续写 ---

要求：
- 直接从断点处续写，不要重复标题或已有内容。
- 保持原有的 Markdown 格式和语言风格。
- 如有搜索源，请继续引用 [来源名称](URL)。
- 务必包含结论或展望章节作为结尾。
"""
    try:
        response = await llm.ainvoke(prompt)
        continuation = response.content.strip()
        anchor = report[-50:].strip()
        if anchor and anchor in continuation:
            idx = continuation.index(anchor) + len(anchor)
            continuation = continuation[idx:].strip()
        combined = report.rstrip() + "\n\n" + continuation
        logger.info(f"报告续写异步完成，原长度={len(report)}，续写后={len(combined)}")
        return combined
    except Exception as e:
        logger.warning(f"报告续写异步失败: {e}")
        return report


# ──────────────────────────────────────────────
# Writer 节点
# ──────────────────────────────────────────────


async def writer_node(state: dict) -> dict:
    """
    异步撰写员节点：基于搜索结果生成 Markdown 报告
    内置质量校验，不合格时自动修复一轮

    Args:
        state: ResearchState 字典，包含 topic, search_results, error 字段

    Returns:
        dict: 包含 draft_report 和 final_report 字段的更新
    """
    topic = state.get("topic", "")
    results = state.get("search_results", [])

    if state.get("error") and not results:
        return {
            "draft_report": "",
            "final_report": "",
            "error": state["error"],
        }

    research_text = json.dumps(results, indent=2, ensure_ascii=False)

    if not results:
        research_text = "未找到相关搜索结果，请基于你的知识生成报告。"

    llm = _build_llm(temperature=0.7)

    # ── 异步生成 ──
    try:
        prompt = _build_prompt(topic, research_text)
        draft = await _generate_report_async(llm, prompt)
    except Exception as e:
        logger.error(f"报告生成失败: {e}")
        return {
            "draft_report": "",
            "final_report": "",
            "error": f"报告生成失败: {e}",
        }

    # ── 校验 ──
    issues = validate_report(draft, topic, results)
    if not issues:
        logger.info("报告质量校验通过")
    else:
        logger.warning(f"报告质量校验未通过 ({len(issues)} 项)，尝试修复: {issues}")
        fix_instruction = (
            "你上次生成的报告存在以下问题，请修正后重新输出：\n"
            + "\n".join(f"- {i}" for i in issues)
            + "\n\n请确保报告结构完整、内容充实。"
        )
        try:
            prompt = _build_prompt(topic, research_text, fix_instruction)
            draft = await _generate_report_async(llm, prompt)
            logger.info("报告修复完成")
        except Exception as e:
            logger.error(f"报告修复失败，使用原始版本: {e}")

    # ── 截断检测与续写 ──
    if _is_truncated(draft):
        logger.warning("检测到报告可能被截断，尝试续写")
        draft = await _continue_report_async(llm, draft, topic, research_text)

    return {"draft_report": draft, "final_report": draft}


# ── 同步别名 (用于 LangGraph invoke 兼容) ──
def writer_node_sync(state: dict) -> dict:
    """同步版本的 writer_node，用于 LangGraph invoke"""
    import asyncio
    return asyncio.run(writer_node(state))
