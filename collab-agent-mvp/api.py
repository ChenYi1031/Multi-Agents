"""
CollabAgent MVP - FastAPI 服务
提供 /research 端点触发多 Agent 协作研究流程
支持异步执行、SSE 流式进度、任务取消
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from pathlib import Path
from typing import AsyncGenerator, Dict

from fastapi import FastAPI, Query, HTTPException
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
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 活跃 SSE 任务追踪与取消信号 ──
# 使用 asyncio.Event 实现取消信号，避免依赖 asyncio.Task 引用


class StreamTask:
    """SSE 流任务元数据"""
    def __init__(self, task_id: str, topic: str):
        self.task_id = task_id
        self.topic = topic
        self.cancel_event = asyncio.Event()
        self.created_at = __import__('time').time()


_active_streams: Dict[str, StreamTask] = {}


def _sse(event: str, data: dict) -> str:
    """格式化一条 SSE 消息（命名事件 + JSON data）"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _sse_safe(event: str, data: dict) -> str:
    """安全版 _sse，确保 data 可 JSON 序列化"""
    try:
        return _sse(event, data)
    except (TypeError, ValueError) as e:
        logger.error(f"SSE 序列化失败: {e}, data keys={list(data.keys())}")
        return _sse("error", {"message": "服务内部错误: 数据序列化失败"})


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
    启动研究任务（非流式）

    接收主题 → 搜索研究员收集信息 → 报告撰写员生成报告 → 返回结果
    使用唯一 thread_id 隔离每次请求的状态。
    """
    logger.info(f"收到研究请求，主题: {req.topic}")
    thread_id = str(uuid.uuid4())

    initial_state = {
        "topic": req.topic,
        "search_results": [],
        "draft_report": "",
        "final_report": "",
        "error": "",
    }

    try:
        final_state = await compiled_graph.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": thread_id}},
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

    except asyncio.CancelledError:
        logger.warning(f"研究任务被取消，主题: {req.topic}")
        return JSONResponse(
            status_code=499,
            content={"status": "cancelled", "detail": "任务已被取消"},
        )
    except Exception as e:
        logger.exception(f"研究过程异常: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "detail": f"服务内部错误: {e}"},
        )


# ── SSE 流式进度端点 ──
async def _check_cancelled(stream_task: StreamTask) -> None:
    """检查取消信号，如已取消则抛出 CancelledError"""
    if stream_task.cancel_event.is_set():
        raise asyncio.CancelledError()


async def _run_research_stream(topic: str, stream_task: StreamTask) -> AsyncGenerator[str, None]:
    """
    生成 SSE 事件流：研究 → 撰写 → 完成（或出错/取消）
    通过 await 直接调用 async node，不阻塞事件循环。
    支持通过 stream_task.cancel_event 实现外部取消。
    """
    state = {
        "topic": topic,
        "search_results": [],
        "draft_report": "",
        "final_report": "",
        "error": "",
    }

    try:
        # ── 阶段1：搜索研究员 ──
        await _check_cancelled(stream_task)
        yield _sse_safe("progress", {
            "stage": "research",
            "message": "🔍 搜索研究员正在收集信息...",
            "task_id": stream_task.task_id,
        })
        research_update = await researcher_node(state)
        state.update(research_update)

        results_count = len(state.get("search_results", []))
        await _check_cancelled(stream_task)
        if state.get("error"):
            yield _sse("error", {"message": state["error"]})
            return

        yield _sse_safe("progress", {
            "stage": "research_done",
            "message": f"✅ 找到 {results_count} 条相关结果",
            "count": results_count,
            "search_results": state.get("search_results", []),
        })

        # ── 阶段2：报告撰写员 ──
        await _check_cancelled(stream_task)
        yield _sse_safe("progress", {
            "stage": "writing",
            "message": "✍️ 报告撰写员正在撰写报告...",
        })
        writer_update = await writer_node(state)
        state.update(writer_update)

        await _check_cancelled(stream_task)
        if state.get("error"):
            yield _sse("error", {"message": state["error"]})
            return

        report = state.get("final_report", "")
        if not report:
            yield _sse("error", {"message": "报告生成结果为空"})
            return

        yield _sse_safe("progress", {
            "stage": "writing_done",
            "message": "✅ 报告生成完成",
        })

        # ── 阶段3：完成，推送最终报告 ──
        yield _sse_safe("complete", {
            "report": report,
            "search_results": state.get("search_results", []),
        })

    except asyncio.CancelledError:
        logger.info(f"SSE 流被取消 (task_id={stream_task.task_id})")
        yield _sse("error", {"message": "研究任务已被取消"})
    except Exception as e:
        logger.exception(f"流式研究过程异常 (task_id={stream_task.task_id}): {e}")
        yield _sse_safe("error", {"message": f"服务内部错误: {e}"})
    finally:
        _active_streams.pop(stream_task.task_id, None)


@app.get("/research/stream")
async def research_stream(topic: str = Query(..., description="研究主题")):
    """
    流式研究端点（SSE）

    实时推送 Agent 工作进度，前端用 EventSource 监听四类命名事件：
    - progress: 各阶段进度（research / research_done / writing / writing_done）
    - complete: 最终报告与搜索结果
    - error:    错误信息

    每个流分配唯一 task_id（通过首个 progress 事件返回），
    可通过 DELETE /research/stream/{task_id} 取消。
    """
    if not topic or not topic.strip():
        raise HTTPException(status_code=400, detail="研究主题不能为空")

    logger.info(f"收到流式研究请求，主题: {topic}")
    stream_task = StreamTask(task_id=str(uuid.uuid4()), topic=topic)
    _active_streams[stream_task.task_id] = stream_task

    async def _event_stream():
        """SSE 事件流生成器"""
        yield _sse("progress", {
            "stage": "starting",
            "message": "🚀 研究任务已创建",
            "task_id": stream_task.task_id,
        })
        async for event in _run_research_stream(topic, stream_task):
            yield event

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "X-Task-Id": stream_task.task_id,
        },
    )


@app.delete("/research/stream/{task_id}")
async def cancel_research_stream(task_id: str):
    """
    取消正在进行的 SSE 流式研究任务。

    通过 task_id 设置取消信号，使 SSE 生成器在下一个检查点优雅退出。
    """
    stream_task = _active_streams.get(task_id)
    if not stream_task:
        raise HTTPException(status_code=404, detail=f"未找到活跃任务: {task_id}")

    stream_task.cancel_event.set()
    logger.info(f"已发送取消信号给任务: {task_id} (主题: {stream_task.topic})")
    return {"status": "cancelling", "task_id": task_id}


@app.get("/research/stream/active")
async def list_active_streams():
    """查看当前活跃的 SSE 流任务列表（管理用）"""
    return {
        "count": len(_active_streams),
        "tasks": [
            {
                "task_id": tid,
                "topic": t.topic,
                "cancelled": t.cancel_event.is_set(),
            }
            for tid, t in _active_streams.items()
        ],
    }


# ── 健康检查 ──
@app.get("/health")
async def health():
    """健康检查端点"""
    from config import OPENAI_API_KEY, TAVILY_API_KEY

    dd_ok = False
    try:
        r = _search_duckduckgo("health", max_results=1)
        dd_ok = bool(r)
    except Exception:
        pass

    return {
        "status": "ok",
        "service": "CollabAgent MVP",
        "version": "2.0.0",
        "checks": {
            "duckduckgo": "available" if dd_ok else "unavailable",
            "tavily": "configured" if _tavily_available() else "not_configured",
            "llm_key": "configured" if OPENAI_API_KEY else "missing",
        },
    }


# ── 前端静态文件托管（生产部署） ──
_DIST_DIR = Path(__file__).resolve().parent / "web" / "dist"
if _DIST_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(_DIST_DIR), html=True), name="web")
    logger.info(f"已挂载前端静态文件: {_DIST_DIR}")
else:
    logger.info("未检测到 web/dist，跳过前端静态托管（开发模式请使用 Vite dev server）")
