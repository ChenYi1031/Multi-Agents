"""
CollabAgent MVP 配置模块
从 .env 文件加载环境变量
"""

import os
from dotenv import load_dotenv

load_dotenv()


# ─── OpenAI 配置 ───────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")

# ─── 搜索配置 ───────────────────────────────────────────────────
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
USE_DUCKDUCKGO = os.getenv("USE_DUCKDUCKGO", "false").lower() == "true"

# ─── 校验 ───────────────────────────────────────────────────────
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY 未设置，请在 .env 文件中配置")

if not USE_DUCKDUCKGO and not TAVILY_API_KEY:
    raise ValueError(
        "TAVILY_API_KEY 未设置。如需使用 DuckDuckGo 免费搜索，"
        "请在 .env 中设置 USE_DUCKDUCKGO=true"
    )
