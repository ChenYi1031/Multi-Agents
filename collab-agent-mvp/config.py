"""
CollabAgent MVP 配置模块
支持 OpenAI 兼容接口（如 DeepSeek）和系统环境变量
"""

from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()


# ─── LLM 配置（OpenAI 兼容接口）──────────────────────────────────
# 优先读取系统环境变量 DEEPSEEK_API_KEY，其次 .env 中的 OPENAI_API_KEY
OPENAI_API_KEY = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY", "")
# DeepSeek 的 OpenAI 兼容 base_url
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com")
OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "deepseek-v4-flash")

# ─── 搜索配置 ───────────────────────────────────────────────────
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
USE_DUCKDUCKGO = os.getenv("USE_DUCKDUCKGO", "true").lower() == "true"

# ─── 校验 ───────────────────────────────────────────────────────
if not OPENAI_API_KEY:
    raise ValueError(
        "API Key 未设置。请通过系统环境变量 DEEPSEEK_API_KEY 或在 .env 中配置 OPENAI_API_KEY"
    )
