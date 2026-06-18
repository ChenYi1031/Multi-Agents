"""
CollabAgent MVP - FastAPI 服务
提供 /research 端点触发多 Agent 协作研究流程
"""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from graph import compiled_graph
from tools.search import _search_duckduckgo, _tavily_available

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="CollabAgent MVP",
    description="多 Agent 协作研究报告生成系统 - 最小可行产品",
    version="1.0.0",
)

# CORS 中间件，方便后续前端调试
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 启动时连通性探针 ──
@app.on_event("startup")
async def startup_probe():
    """服务启动时检查搜索链路是否可用（不影响启动）"""
    logger.info("运行搜索连通性探针...")
    try:
        t0 = time.time()
        results = _search_duckduckgo("test", max_results=1)
        elapsed = time.time() - t0
        if results:
            logger.info(f"✓ DuckDuckGo 搜索可用 ({elapsed:.1f}s)")
        else:
            logger.warning(f"⚠ DuckDuckGo 搜索无返回 ({elapsed:.1f}s)")
    except Exception as e:
        logger.warning(f"⚠ DuckDuckGo 搜索不可用: {e}")

    tavily_ok = _tavily_available()
    if tavily_ok:
        logger.info("✓ Tavily API Key 已配置，可用")
    else:
        logger.info("ℹ Tavily 未配置，DD 失败时将用 LLM 知识兜底")


class ResearchRequest(BaseModel):
    """研究请求体"""
    topic: str


@app.post("/research")
async def research(req: ResearchRequest):
    """
    启动研究任务

    接收主题 → 搜索研究员收集信息 → 报告撰写员生成报告 → 返回结果
    """
    logger.info(f"收到研究请求，主题: {req.topic}")

    initial_state = {
        "topic": req.topic,
        "search_results": [],
        "draft_report": "",
        "final_report": "",
        "error": "",
    }

    try:
        final_state = compiled_graph.invoke(
            initial_state,
            config={"configurable": {"thread_id": "1"}},
        )

        if final_state.get("error"):
            logger.error(f"研究过程出错: {final_state['error']}")
            return JSONResponse(
                status_code=500,
                content={"status": "error", "detail": final_state["error"]},
            )

        logger.info(f"研究报告生成完成，主题: {req.topic}")
        return {
            "status": "completed",
            "final_report": final_state["final_report"],
            "search_results": final_state["search_results"],
        }

    except Exception as e:
        logger.exception(f"研究过程异常: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "detail": f"服务内部错误: {e}"},
        )


@app.get("/health")
async def health():
    """健康检查端点"""
    from config import OPENAI_API_KEY, TAVILY_API_KEY

    # 快速连通性自检（不阻塞）
    dd_ok = False
    try:
        r = _search_duckduckgo("health", max_results=1)
        dd_ok = bool(r)
    except Exception:
        pass

    return {
        "status": "ok",
        "service": "CollabAgent MVP",
        "checks": {
            "duckduckgo": "available" if dd_ok else "unavailable",
            "tavily": "configured" if _tavily_available() else "not_configured",
            "llm_key": "configured" if OPENAI_API_KEY else "missing",
        },
    }
