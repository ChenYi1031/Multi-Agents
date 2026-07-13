"""
事实校验员 Agent 节点
检查报告中的每个主张是否有可靠来源支撑
标记无来源/弱来源的主张，给出修正建议
支持异步执行 + token 用量追踪
"""

from __future__ import annotations

import json
import logging
import re
from typing import List

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL_NAME
from tools.token_tracker import TokenUsageTracker, _extract_token_usage, extract_model_name

logger = logging.getLogger(__name__)


FACT_CHECKER_PROMPT = """你是一位严谨的事实核查员。你的任务是对一份研究报告进行事实核查。

请逐一检查报告中的每条主张（claim），判断：
1. **有来源支撑** — 主张后有明确的来源引用 [名称](URL)
2. **部分支撑** — 主张有部分依据，但引用不充分
3. **无来源** — 主张完全没有来源引用

输出格式为 JSON 数组，每个元素包含：
- "claim": 主张内容（原文引用）
- "status": "verified" | "partial" | "unverified"
- "evidence": 支撑证据或说明
- "suggestion": 如无来源，给出补充建议

最后给出总体评分：总分 10 分制，基于来源覆盖率和报告可靠性。"""


def _build_llm(model_name: str | None = None, api_key: str | None = None, base_url: str | None = None, **kwargs):
    return ChatOpenAI(
        model=model_name or OPENAI_MODEL_NAME,
        api_key=api_key or OPENAI_API_KEY,
        base_url=base_url or OPENAI_BASE_URL,
        **kwargs,
    )


async def fact_checker_node(state: dict) -> dict:
    """
    事实校验节点：检查报告中的主张是否有可靠来源

    Args:
        state: 包含 topic, search_results, draft_report, model_name 等

    Returns:
        dict: 包含 fact_check_report 字段
    """
    report = state.get("draft_report") or state.get("final_report", "")
    topic = state.get("topic", "")
    results = state.get("search_results", [])

    if not report:
        return {"fact_check_report": "", "error": "没有报告可核查"}

    model_name = state.get("model_name") or None
    api_key = state.get("api_key") or None
    base_url = state.get("api_base_url") or None
    llm = _build_llm(model_name=model_name, api_key=api_key, base_url=base_url, temperature=0.2)
    tracker = TokenUsageTracker(agent="fact_checker")

    sources_text = json.dumps(results, indent=2, ensure_ascii=False) if results else "无搜索结果"

    messages = [
        SystemMessage(content=FACT_CHECKER_PROMPT),
        HumanMessage(content=f"""
研究主题：{topic}

搜索结果（来源）：
{sources_text}

研究报告内容：
{report}

请对上述报告进行事实核查，输出 JSON 数组格式的结果。
"""),
    ]

    try:
        tracker.start_call()
        response = await llm.ainvoke(messages)
        input_t, output_t = _extract_token_usage(response)
        model = extract_model_name(response) or model_name or OPENAI_MODEL_NAME
        tracker.end_call(model, input_t, output_t)

        raw = response.content.strip()
        # 尝试提取 JSON
        json_match = re.search(r'\[.*\]', raw, re.DOTALL)
        if json_match:
            fact_checks = json.loads(json_match.group())
        else:
            fact_checks = [{"claim": "解析错误", "status": "unverified", "evidence": "无法解析 LLM 输出", "suggestion": "重试"}]

        # 计算评分
        total = len(fact_checks)
        verified = sum(1 for c in fact_checks if c.get("status") == "verified")
        partial = sum(1 for c in fact_checks if c.get("status") == "partial")
        score = round((verified * 10 + partial * 6) / max(total, 1), 1)

        fact_check_report = {
            "score": score,
            "total_claims": total,
            "verified": verified,
            "partial": partial,
            "unverified": total - verified - partial,
            "details": fact_checks,
        }

        return {
            "fact_check_report": json.dumps(fact_check_report, ensure_ascii=False, indent=2),
            "token_usage": tracker.get_summary(),
        }
    except Exception as e:
        logger.error(f"事实核查失败: {e}")
        return {
            "fact_check_report": json.dumps({
                "score": 0,
                "error": str(e),
                "details": [],
            }, ensure_ascii=False),
            "token_usage": tracker.get_summary(),
        }
