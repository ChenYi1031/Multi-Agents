"""
CollabAgent MVP - FastAPI 服务
提供 /research 端点触发多 Agent 协作研究流程
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agents.researcher import researcher_node
from agents.writer import writer_node
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


# ── 启动时连通性检查 ──
@app.on_event("startup")
async def startup_probe():
    """快速检查搜索链路配置状态（不阻塞启动）"""
    tavily_ok = _tavily_available()
    proxy = os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY") or "无"
    logger.info(f"搜索配置: DD={os.getenv('USE_DUCKDUCKGO','true')}, Tavily={'已配置' if tavily_ok else '未配置'}, 代理={proxy}")
    if tavily_ok:
        logger.info("✓ Tavily API Key 已配置")
    else:
        logger.info("ℹ Tavily 未配置，搜索失败时 LLM 知识兜底")


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


# ── SSE 流式进度端点 ──
# Agent 执行可能耗时数十秒，此端点通过 Server-Sent Events 实时推送各阶段进度，
# 前端无需长时间空等。直接编排 researcher_node → writer_node，复用现有 ResearchState，
# 不改动 graph.py / agents 内部逻辑。
def _sse(event: str, data: dict) -> str:
    """格式化一条 SSE 消息（命名事件 + JSON data）"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _run_research_stream(topic: str) -> AsyncGenerator[str, None]:
    """生成 SSE 事件流：研究 → 撰写 → 完成（或出错）"""
    state = {
        "topic": topic,
        "search_results": [],
        "draft_report": "",
        "final_report": "",
        "error": "",
    }

    try:
        # ── 阶段1：搜索研究员 ──
        yield _sse("progress", {
            "stage": "research",
            "message": "🔍 搜索研究员正在收集信息...",
        })
        loop = asyncio.get_event_loop()
        research_update = await loop.run_in_executor(None, researcher_node, state)
        state.update(research_update)

        results_count = len(state.get("search_results", []))
        if state.get("error"):
            yield _sse("error", {"message": state["error"]})
            return

        yield _sse("progress", {
            "stage": "research_done",
            "message": f"✅ 找到 {results_count} 条相关结果",
            "count": results_count,
            "search_results": state.get("search_results", []),
        })

        # ── 阶段2：报告撰写员 ──
        yield _sse("progress", {
            "stage": "writing",
            "message": "✍️ 报告撰写员正在撰写报告...",
        })
        writer_update = await loop.run_in_executor(None, writer_node, state)
        state.update(writer_update)

        if state.get("error"):
            yield _sse("error", {"message": state["error"]})
            return

        report = state.get("final_report", "")
        if not report:
            yield _sse("error", {"message": "报告生成结果为空"})
            return

        yield _sse("progress", {
            "stage": "writing_done",
            "message": "✅ 报告生成完成",
        })

        # ── 阶段3：完成，推送最终报告 ──
        yield _sse("complete", {
            "report": report,
            "search_results": state.get("search_results", []),
        })

    except Exception as e:
        logger.exception(f"流式研究过程异常: {e}")
        yield _sse("error", {"message": f"服务内部错误: {e}"})


@app.get("/research/stream")
async def research_stream(topic: str = Query(..., description="研究主题")):
    """
    流式研究端点（SSE）

    实时推送 Agent 工作进度，前端用 EventSource 监听三类命名事件：
    - progress: 各阶段进度（research / research_done / writing / writing_done）
    - complete: 最终报告与搜索结果
    - error:    错误信息（仅失败时，流随之结束）
    """
    logger.info(f"收到流式研究请求，主题: {topic}")
    return StreamingResponse(
        _run_research_stream(topic),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
            "Connection": "keep-alive",
        },
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


# ── 前端静态文件托管（生产部署） ──
# 开发时前端跑在 Vite dev server，生产时 npm run build 产出 web/dist，
# 由 FastAPI 在根路径托管，实现单服务部署（前端与 API 同源，无跨域问题）。
# 仅当 dist 目录存在时挂载，避免开发期启动报错。
_DIST_DIR = Path(__file__).resolve().parent / "web" / "dist"
if _DIST_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(_DIST_DIR), html=True), name="web")
    logger.info(f"已挂载前端静态文件: {_DIST_DIR}")
else:
    logger.info("未检测到 web/dist，跳过前端静态托管（开发模式请使用 Vite dev server）")
