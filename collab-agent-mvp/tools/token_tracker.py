"""
Token 用量追踪模块
使用 LangChain BaseCallbackHandler 捕获 LLM 调用的 token 消耗
支持按 Agent 拆分展示，提供成本估算（DeepSeek 计价）
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from langchain_core.callbacks import BaseCallbackHandler

logger = logging.getLogger(__name__)

# ── 模型计价（元 / 百万 tokens） ──
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    "deepseek-v4-flash": {
        "input": 0.14,
        "output": 0.28,
        "cache_read": 0.028,
    },
    "deepseek-v4-pro": {
        "input": 1.74,
        "output": 3.48,
    },
    # 兜底默认
    "default": {
        "input": 0.14,
        "output": 0.28,
    },
}

# ── 已知的 DeepSeek 模型别名 ──
DEEPSEEK_MODEL_ALIASES = {
    "deepseek-chat": "deepseek-v4-flash",
    "deepseek-v4-flash": "deepseek-v4-flash",
    "deepseek-v4-pro": "deepseek-v4-pro",
    "deepseek-reasoner": "deepseek-v4-pro",
}


def _normalize_model(model: str) -> str:
    """将模型名称归一化为已知的定价 key"""
    raw = model.lower().strip()
    for alias, canonical in DEEPSEEK_MODEL_ALIASES.items():
        if alias in raw:
            return canonical
    return model


def _calc_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """估算单次调用的成本（元）"""
    pricing = MODEL_PRICING.get(_normalize_model(model), MODEL_PRICING["default"])
    input_cost = (input_tokens / 1_000_000) * pricing.get("input", 0.14)
    output_cost = (output_tokens / 1_000_000) * pricing.get("output", 0.28)
    return round(input_cost + output_cost, 6)


@dataclass
class TokenCallRecord:
    """单次 LLM 调用的记录"""
    agent: str
    model: str
    input_tokens: int
    output_tokens: int
    duration_ms: float

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def cost(self) -> float:
        return _calc_cost(self.model, self.input_tokens, self.output_tokens)

    def to_dict(self) -> dict:
        return {
            "agent": self.agent,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "duration_ms": round(self.duration_ms, 1),
            "cost": self.cost,
        }


class TokenUsageTracker:
    """
    Token 用量追踪器
    收集一次 Research 会话中的所有 LLM 调用记录

    用法：
        tracker = TokenUsageTracker(agent="researcher")
        # 在 LLM 调用前后调用
        tracker.start_call()
        response = await llm.ainvoke(...)
        tracker.end_call(response)
    """

    def __init__(self, agent: str = "unknown"):
        self.agent = agent
        self.calls: List[TokenCallRecord] = []
        self._current_start: Optional[float] = None

    def start_call(self):
        """记录 LLM 调用开始时间"""
        self._current_start = time.monotonic()

    def end_call(self, model: str, input_tokens: int = 0, output_tokens: int = 0) -> TokenCallRecord:
        """
        完成一次 LLM 调用记录

        Args:
            model: 模型名称
            input_tokens: prompt tokens 数
            output_tokens: completion tokens 数

        Returns:
            TokenCallRecord
        """
        duration = 0.0
        if self._current_start is not None:
            duration = (time.monotonic() - self._current_start) * 1000
            self._current_start = None

        record = TokenCallRecord(
            agent=self.agent,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            duration_ms=duration,
        )
        self.calls.append(record)
        return record

    @property
    def total_input_tokens(self) -> int:
        return sum(c.input_tokens for c in self.calls)

    @property
    def total_output_tokens(self) -> int:
        return sum(c.output_tokens for c in self.calls)

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    @property
    def total_cost(self) -> float:
        return round(sum(c.cost for c in self.calls), 6)

    def get_summary(self) -> dict:
        return {
            "agent": self.agent,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
            "call_count": len(self.calls),
            "calls": [c.to_dict() for c in self.calls],
        }


def _extract_token_usage(response) -> tuple:
    """
    从 LLM 响应中提取 token 使用量

    Args:
        response: AIMessage 对象

    Returns:
        (input_tokens, output_tokens) 元组，无法提取时返回 (0, 0)
    """
    try:
        if not hasattr(response, "response_metadata") or not response.response_metadata:
            raise ValueError("no response_metadata")
        meta = response.response_metadata

        # 防御: MagicMock 的 .get() 返回 MagicMock 而非默认值
        if not isinstance(meta, dict):
            raise ValueError(f"response_metadata 类型异常: {type(meta).__name__}")

        # OpenAI 兼容格式
        usage = meta.get("token_usage", {})
        if usage and isinstance(usage, dict):
            prompt = usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0)
            completion = usage.get("completion_tokens", 0) or usage.get("output_tokens", 0)
            prompt = prompt if isinstance(prompt, int) else 0
            completion = completion if isinstance(completion, int) else 0
            if prompt or completion:
                return (prompt, completion)

        # 某些兼容接口可能直接放在顶层
        prompt = meta.get("prompt_tokens", 0) or meta.get("input_tokens", 0)
        completion = meta.get("completion_tokens", 0) or meta.get("output_tokens", 0)
        prompt = prompt if isinstance(prompt, int) else 0
        completion = completion if isinstance(completion, int) else 0
        if prompt or completion:
            return (prompt, completion)

        # 从 usage_metadata（LangChain 0.3+ 新增）提取
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            um = response.usage_metadata
            if isinstance(um, dict):
                input_t = um.get("input_tokens", 0)
                output_t = um.get("output_tokens", 0)
                input_t = input_t if isinstance(input_t, int) else 0
                output_t = output_t if isinstance(output_t, int) else 0
                return (input_t, output_t)
    except Exception as e:
        logger.debug(f"提取 token 用量失败: {e}")

    return (0, 0)


def extract_model_name(response) -> str:
    """从 LLM 响应中提取模型名称"""
    try:
        if not hasattr(response, "response_metadata") or not response.response_metadata:
            return ""
        meta = response.response_metadata
        if not isinstance(meta, dict):
            return ""
        name = meta.get("model_name", "") or meta.get("model", "")
        return name if isinstance(name, str) else ""
    except Exception:
        pass
    return ""
