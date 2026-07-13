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

from fastapi import FastAPI, Query, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agents.researcher import researcher_node
from agents.writer import writer_node
from agents.fact_checker import fact_checker_node
from graph import compiled_graph
from tools.search import _search_duckduckgo, _tavily_available
from tools.rag import add_knowledge_file, search_knowledge, get_knowledge_base

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


def _make_initial_state(topic: str, **extra) -> dict:
    """创建带默认值的初始 ResearchState"""
    return {
        "topic": topic,
        "search_results": [],
        "draft_report": "",
        "final_report": "",
        "error": "",
        "token_usage": {},
        "followup_question": "",
        "conversation_history": [],
        "model_name": extra.get("model_name", ""),
        "search_source": extra.get("search_source", ""),
        "api_base_url": extra.get("api_base_url", ""),
        "api_key": extra.get("api_key", ""),
        "api_format": extra.get("api_format", ""),
        "fact_check_report": "",
        "knowledge_docs": [],
        "use_llm": extra.get("use_llm", True),
    }


def _merge_token_usage(*usages: dict) -> dict:
    """
    合并多个 token_usage 字典，汇总统计和 calls 列表。
    用于累加 researcher + writer 两个节点的 token 用量。
    """
    merged = {
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_tokens": 0,
        "total_cost": 0.0,
        "call_count": 0,
        "calls": [],
    }
    for u in usages:
        if not u:
            continue
        merged["total_input_tokens"] += u.get("total_input_tokens", 0) or 0
        merged["total_output_tokens"] += u.get("total_output_tokens", 0) or 0
        merged["total_tokens"] += u.get("total_tokens", 0) or 0
        merged["total_cost"] += u.get("total_cost", 0) or 0
        merged["call_count"] += u.get("call_count", 0) or 0
        merged["calls"].extend(u.get("calls", []) or [])

    # 重建 agent_breakdown（如果原始数据有 agent 字段）
    agent_map = {}
    for c in merged["calls"]:
        agent = c.get("agent", "unknown")
        if agent not in agent_map:
            agent_map[agent] = {
                "agent": agent,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_tokens": 0,
                "total_cost": 0.0,
                "call_count": 0,
            }
        agent_map[agent]["total_input_tokens"] += c.get("input_tokens", 0) or 0
        agent_map[agent]["total_output_tokens"] += c.get("output_tokens", 0) or 0
        agent_map[agent]["total_tokens"] += c.get("total_tokens", 0) or 0
        agent_map[agent]["total_cost"] += c.get("cost", 0) or 0
        agent_map[agent]["call_count"] += 1

    merged["agent_breakdown"] = list(agent_map.values()) if agent_map else []
    merged["total_cost"] = round(merged["total_cost"], 6)
    return merged


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


# ── Settings 存储（服务端 settings.json） ──
_SETTINGS_FILE = Path(__file__).resolve().parent / "settings.json"


def _load_settings() -> dict:
    """读取 settings.json，不存在时返回默认结构"""
    if _SETTINGS_FILE.exists():
        try:
            return json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"settings.json 读取失败: {e}")
    return {"providers": [], "active_provider_id": ""}


def _save_settings(data: dict) -> None:
    """写入 settings.json"""
    _SETTINGS_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


@app.get("/settings")
async def get_settings():
    """读取供应商配置"""
    return _load_settings()


@app.post("/settings")
async def post_settings(data: dict):
    """保存供应商配置"""
    try:
        _save_settings(data)
        return {"status": "ok"}
    except Exception as e:
        logger.exception(f"保存 settings 失败: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})


@app.delete("/settings")
async def delete_settings():
    """重置 settings.json 为默认值"""
    _save_settings({"providers": [], "active_provider_id": ""})
    return {"status": "ok", "message": "配置已重置"}


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

    initial_state = _make_initial_state(req.topic)

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

        # 合并所有节点的 token_usage
        token_usage = _merge_token_usage(final_state.get("token_usage", {}))
        fact_check_raw = final_state.get("fact_check_report", "")
        fact_check_data = {}
        if fact_check_raw:
            try:
                fact_check_data = json.loads(fact_check_raw)
            except (json.JSONDecodeError, TypeError):
                fact_check_data = {"raw": fact_check_raw}

        logger.info(f"研究报告生成完成，主题: {req.topic}")
        return {
            "status": "completed",
            "final_report": final_state["final_report"],
            "search_results": final_state["search_results"],
            "token_usage": token_usage,
            "fact_check": fact_check_data,
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


async def _run_research_stream(
    topic: str,
    stream_task: StreamTask,
    model_name: str = "",
    search_source: str = "",
    api_base_url: str = "",
    api_key: str = "",
    api_format: str = "",
    use_llm: bool = True,
) -> AsyncGenerator[str, None]:
    """
    生成 SSE 事件流：研究 → 撰写 → 事实核查 → 完成（或出错/取消）
    通过 await 直接调用 async node，不阻塞事件循环。
    支持通过 stream_task.cancel_event 实现外部取消。
    支持动态 model_name/search_source 和供应商 API 配置。
    当 use_llm=False 时，跳过 LLM 调用，仅使用搜索 + 模板报告。
    """
    state = _make_initial_state(
        topic,
        model_name=model_name,
        search_source=search_source,
        api_base_url=api_base_url,
        api_key=api_key,
        api_format=api_format,
        use_llm=use_llm,
    )

    # 超时控制：总流程最多 300 秒，每个节点最多 120 秒
    _NODE_TIMEOUT = 120
    _TOTAL_TIMEOUT = 300
    _start_time = __import__('time').time()

    async def _timeout_check():
        """检查总耗时是否超限"""
        if __import__('time').time() - _start_time > _TOTAL_TIMEOUT:
            raise asyncio.TimeoutError(f"研究任务总用时超过 {_TOTAL_TIMEOUT} 秒")

    try:
        # ── 阶段1：搜索研究员 ──
        await _check_cancelled(stream_task)
        yield _sse_safe("progress", {
            "stage": "research",
            "message": "🔍 搜索研究员正在收集信息...",
            "task_id": stream_task.task_id,
        })
        try:
            research_update = await asyncio.wait_for(researcher_node(state), timeout=_NODE_TIMEOUT)
        except asyncio.TimeoutError:
            yield _sse_safe("error", {"message": f"⏰ 搜索阶段超时（超过 {_NODE_TIMEOUT} 秒），请检查 API Key 和网络配置"})
            return
        state.update(research_update)
        await _timeout_check()

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
            "token_usage": state.get("token_usage", {}),
        })

        # ── 阶段2：报告撰写员 ──
        await _check_cancelled(stream_task)
        yield _sse_safe("progress", {
            "stage": "writing",
            "message": "✍️ 报告撰写员正在撰写报告...",
        })
        try:
            writer_update = await asyncio.wait_for(writer_node(state), timeout=_NODE_TIMEOUT)
        except asyncio.TimeoutError:
            yield _sse_safe("error", {"message": f"⏰ 报告撰写阶段超时（超过 {_NODE_TIMEOUT} 秒），请检查 API Key 和网络配置"})
            return
        merged_token_usage = _merge_token_usage(
            state.get("token_usage", {}),
            writer_update.get("token_usage", {}),
        )
        writer_update.pop("token_usage", None)
        state.update(writer_update)
        state["token_usage"] = merged_token_usage
        await _timeout_check()

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
            "token_usage": merged_token_usage,
        })

        # ── 阶段3：事实核查（仅 when use_llm=True） ──
        fact_check_data = {}
        if state.get("use_llm", True):
            await _check_cancelled(stream_task)
            yield _sse_safe("progress", {
                "stage": "fact_check",
                "message": "🔍 事实核查员正在校验报告...",
            })
            try:
                fact_check_update = await asyncio.wait_for(fact_checker_node(state), timeout=_NODE_TIMEOUT)
            except asyncio.TimeoutError:
                yield _sse_safe("error", {"message": f"⏰ 事实核查阶段超时（超过 {_NODE_TIMEOUT} 秒），请检查 API Key 和网络配置"})
                return
            merged_token_usage = _merge_token_usage(
                merged_token_usage,
                fact_check_update.get("token_usage", {}),
            )
            fact_check_update.pop("token_usage", None)
            state.update(fact_check_update)
            state["token_usage"] = merged_token_usage
            await _timeout_check()

            fact_check_raw = state.get("fact_check_report", "")
            if fact_check_raw:
                try:
                    fact_check_data = json.loads(fact_check_raw)
                except (json.JSONDecodeError, TypeError):
                    fact_check_data = {"raw": fact_check_raw}

            yield _sse_safe("progress", {
                "stage": "fact_check_done",
                "message": f"✅ 事实核查完成：{fact_check_data.get('verified', 0)}/{fact_check_data.get('total_claims', 0)} 条主张已验证",
                "fact_check": fact_check_data,
                "token_usage": merged_token_usage,
            })
        else:
            yield _sse_safe("progress", {
                "stage": "fact_check_done",
                "message": "⏭️ 事实核查已跳过（无 LLM 模式）",
                "token_usage": merged_token_usage,
            })

        # ── 阶段4：完成 ──
        yield _sse_safe("complete", {
            "report": report,
            "search_results": state.get("search_results", []),
            "token_usage": merged_token_usage,
            "fact_check": fact_check_data,
        })

    except asyncio.CancelledError:
        logger.info(f"SSE 流被取消 (task_id={stream_task.task_id})")
        yield _sse("error", {"message": "研究任务已被取消"})
    except asyncio.TimeoutError:
        logger.warning(f"SSE 流超时 (task_id={stream_task.task_id})")
        yield _sse_safe("error", {"message": f"⏰ 研究任务总用时超过 {_TOTAL_TIMEOUT} 秒，已自动终止"})
    except Exception as e:
        logger.exception(f"流式研究过程异常 (task_id={stream_task.task_id}): {e}")
        yield _sse_safe("error", {"message": f"服务内部错误: {e}"})
    finally:
        _active_streams.pop(stream_task.task_id, None)


@app.get("/research/stream")
async def research_stream(
    topic: str = Query(..., description="研究主题"),
    model_name: str = Query(default="", description="模型名称"),
    search_source: str = Query(default="", description="搜索源 (DuckDuckGo / Tavily)"),
    api_base_url: str = Query(default="", description="自定义 API Base URL（供应商配置）"),
    api_key: str = Query(default="", description="自定义 API Key（供应商配置）"),
    api_format: str = Query(default="", description="API 格式 (openai / anthropic)"),
    use_llm: str = Query(default="true", description="是否启用 LLM 参与 (true/false)"),
):
    """
    流式研究端点（SSE）

    实时推送 Agent 工作进度，前端用 EventSource 监听命名事件：
    - progress: 各阶段进度
    - complete: 最终报告与搜索结果
    - error:    错误信息

    支持通过 model_name 和 search_source 动态配置。
    每个流分配唯一 task_id，可通过 DELETE /research/stream/{task_id} 取消。
    """
    if not topic or not topic.strip():
        raise HTTPException(status_code=400, detail="研究主题不能为空")

    use_llm_bool = use_llm.lower() == "true"

    logger.info(f"收到流式研究请求, 主题={topic}, model={model_name or 'default'}, source={search_source or 'default'}, use_llm={use_llm_bool}")
    stream_task = StreamTask(task_id=str(uuid.uuid4()), topic=topic)
    _active_streams[stream_task.task_id] = stream_task

    async def _event_stream():
        yield _sse("progress", {
            "stage": "starting",
            "message": "🚀 研究任务已创建",
            "task_id": stream_task.task_id,
            "model_name": model_name or "default",
            "search_source": search_source or "default",
            "use_llm": use_llm_bool,
        })
        async for event in _run_research_stream(
            topic, stream_task,
            model_name=model_name,
            search_source=search_source,
            api_base_url=api_base_url,
            api_key=api_key,
            api_format=api_format,
            use_llm=use_llm_bool,
        ):
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


# ── RAG 知识库管理 ──
UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


@app.post("/knowledge/upload")
async def knowledge_upload(file: UploadFile = File(...)):
    """上传知识库文件 (multipart/form-data)"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    ext = Path(file.filename).suffix.lower()
    if ext not in (".txt", ".pdf"):
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: {ext}，仅支持 .txt 和 .pdf")

    try:
        content = await file.read()
        tmp_path = UPLOAD_DIR / file.filename
        tmp_path.write_bytes(content)

        doc_id = add_knowledge_file(str(tmp_path))
        kb = get_knowledge_base()

        logger.info(f"知识库文件上传成功: {file.filename} (doc_id={doc_id})")
        return {
            "status": "ok",
            "doc_id": doc_id,
            "filename": file.filename,
            "chunks_count": sum(1 for c in kb.get_all_chunks() if c["doc_id"] == doc_id),
        }
    except Exception as e:
        logger.exception(f"知识库文件上传失败: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "detail": f"文件处理失败: {e}"})


@app.get("/knowledge/search")
async def knowledge_search(q: str = Query(default="", description="搜索关键词"), top_k: int = Query(default=5)):
    """搜索知识库"""
    if not q:
        return {"results": [], "total_chunks": len(get_knowledge_base().get_all_chunks())}
    results = search_knowledge(q, top_k=top_k)
    return {"results": results, "total_chunks": len(get_knowledge_base().get_all_chunks())}


@app.get("/knowledge/list")
async def knowledge_list():
    """列出所有知识库文档块"""
    return {"chunks": get_knowledge_base().get_all_chunks(), "count": len(get_knowledge_base().get_all_chunks())}


@app.delete("/knowledge/clear")
async def knowledge_clear():
    """清空知识库"""
    get_knowledge_base().clear()
    return {"status": "ok", "message": "知识库已清空"}


# ── 多轮对话追问 ──
class FollowUpRequest(BaseModel):
    """追问请求体"""
    topic: str
    followup_question: str
    previous_report: str = ""
    search_results: list = []
    model_name: str = ""
    search_source: str = ""
    api_base_url: str = ""
    api_key: str = ""
    api_format: str = ""
    use_llm: bool = True


@app.post("/research/followup")
async def research_followup(req: FollowUpRequest):
    """
    对已有研究报告发起追问。

    保留原始上下文，追加 followup_question，
    Researcher 增量搜索后 Writer 更新报告。
    """
    logger.info(f"收到追问请求，主题: {req.topic}, 追问: {req.followup_question}")
    thread_id = str(uuid.uuid4())

    initial_state = _make_initial_state(
        req.topic,
        model_name=req.model_name,
        search_source=req.search_source,
        api_base_url=req.api_base_url,
        api_key=req.api_key,
        api_format=req.api_format,
        use_llm=req.use_llm,
    )
    initial_state["followup_question"] = req.followup_question
    initial_state["conversation_history"] = [
        {"role": "user", "content": req.topic},
        {"role": "assistant", "content": req.previous_report},
        {"role": "user", "content": req.followup_question},
    ]
    # 复用已有搜索结果
    initial_state["search_results"] = req.search_results

    try:
        final_state = await compiled_graph.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": thread_id}},
        )

        if final_state.get("error"):
            return JSONResponse(
                status_code=500,
                content={"status": "error", "detail": final_state["error"]},
            )

        token_usage = _merge_token_usage(final_state.get("token_usage", {}))
        return {
            "status": "completed",
            "final_report": final_state["final_report"],
            "search_results": final_state["search_results"],
            "token_usage": token_usage,
            "fact_check": json.loads(final_state.get("fact_check_report", "{}") or "{}"),
        }
    except Exception as e:
        logger.exception(f"追问处理异常: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "detail": f"追问处理失败: {e}"},
        )


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


# ── 报告导出 ──
@app.post("/research/export/html")
async def export_html(req: ResearchRequest):
    """
    将 Markdown 报告导出为 HTML 文件
    浏览器打开后可 Ctrl+P → 另存为 PDF
    """
    try:
        import markdown as md_lib
        html_content = md_lib.markdown(req.topic, extensions=["fenced_code", "tables", "codehilite"])
        styled_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8">
<title>研究报告</title>
<style>
  body {{ font-family: 'Segoe UI', Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 40px; line-height: 1.8; color: #333; }}
  h1 {{ font-size: 24px; border-bottom: 2px solid #409eff; padding-bottom: 8px; color: #1a1a2e; }}
  h2 {{ font-size: 20px; margin-top: 24px; color: #303133; }}
  h3 {{ font-size: 16px; color: #606266; }}
  code {{ background: #f5f7fa; padding: 2px 6px; border-radius: 4px; }}
  pre {{ background: #f5f7fa; padding: 16px; border-radius: 8px; overflow-x: auto; }}
  blockquote {{ border-left: 4px solid #409eff; margin: 16px 0; padding: 8px 16px; background: #f0f9ff; }}
  table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
  th, td {{ border: 1px solid #dcdfe6; padding: 8px 12px; text-align: left; }}
  th {{ background: #f5f7fa; }}
  @media print {{ body {{ padding: 20px; }} }}
</style>
</head>
<body>{html_content}</body></html>"""
        from fastapi.responses import Response
        return Response(
            content=styled_html.encode("utf-8"),
            media_type="text/html; charset=utf-8",
            headers={ "Content-Disposition": 'attachment; filename="research-report.html"' },
        )
    except Exception as e:
        logger.exception(f"HTML 导出失败: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "detail": f"HTML 导出失败: {e}"})


@app.post("/research/export/markdown")
async def export_markdown(req: ResearchRequest):
    """导出 Markdown 源文件"""
    from fastapi.responses import Response
    return Response(
        content=req.topic.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={ "Content-Disposition": 'attachment; filename="research-report.md"' },
    )


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
