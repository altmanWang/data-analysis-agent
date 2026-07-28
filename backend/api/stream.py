# backend/api/stream.py
"""SSE 流式端点 + Resume 端点
POST /api/threads/{tid}/stream — 发送消息并流式返回
POST /api/threads/{tid}/resume — ask_user 中断后恢复执行
"""

from __future__ import annotations

import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, AsyncIterator

from fastapi import APIRouter, HTTPException, Request as FastAPIRequest
from fastapi.responses import StreamingResponse

from agent.pool import agent_pool
from config import STREAM_CONFIG
from db import get_connection
from services.session_manager import session_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/threads", tags=["stream"])

_db_executor = ThreadPoolExecutor(max_workers=STREAM_CONFIG["db_executor_workers"])


def _fire_and_forget(coro):
    task = asyncio.create_task(coro)
    task.add_done_callback(lambda t: logger.exception("后台任务异常", exc_info=t.exception()) if t.exception() else None)
    return task


def _save_message_sync(thread_id: str, role: str, content: str = "", **kwargs) -> None:
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO message_history (session_id, role, content, thinking_content, tool_name, "
                "tool_args, tool_result, tool_status) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    thread_id, role, content[:STREAM_CONFIG["content_truncate"]] if content else "",
                    kwargs.get("thinking_content", "")[:STREAM_CONFIG["thinking_truncate"]],
                    kwargs.get("tool_name"), kwargs.get("tool_args"),
                    kwargs.get("tool_result"), kwargs.get("tool_status"),
                ),
            )
            conn.commit()
    except Exception:
        logger.exception("保存消息失败 thread_id=%s role=%s", thread_id, role)
    finally:
        if conn:
            conn.close()


async def _save_message(thread_id: str, role: str, content: str = "", **kwargs) -> None:
    loop = asyncio.get_running_loop()
    loop.run_in_executor(
        _db_executor,
        lambda: _save_message_sync(thread_id, role, content, **kwargs),
    )


async def _stream_events(agent, config: dict, content: str | None, thread_id: str) -> AsyncIterator[str]:
    """流式输出 agent 事件，并检测 interrupt"""
    current_text_parts: list[str] = []
    current_thinking_parts: list[str] = []
    pending_tools: dict[str, dict] = {}

    try:
        async for event in agent.astream_events(
            {"messages": [{"role": "user", "content": content}]} if content else {},
            config=config,
            version="v2",
        ):
            evt_type: str = event.get("event", "")
            evt_data: dict[str, Any] = event.get("data", {})

            if evt_type == "on_chat_model_stream":
                chunk = evt_data.get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    current_text_parts.append(chunk.content)
                    yield f"data: {json.dumps({'type': 'text', 'content': chunk.content})}\n\n"
                reasoning = getattr(chunk, "response_metadata", {}).get("reasoning_content", "")
                if reasoning:
                    current_thinking_parts.append(reasoning)
                    yield f"data: {json.dumps({'type': 'thinking', 'content': reasoning})}\n\n"

            elif evt_type == "on_tool_start":
                run_id: str = event.get("run_id", "")
                pending_tools[run_id] = {
                    "name": event.get("name", ""),
                    "input": evt_data.get("input", {}),
                }

            elif evt_type == "on_tool_end":
                run_id = event.get("run_id", "")
                tool = pending_tools.pop(run_id, {})
                name = tool.get("name", event.get("name", ""))
                raw_input = tool.get("input", {})
                raw_output: Any = evt_data.get("output", {})

                if hasattr(raw_output, "content"):
                    out_str = str(raw_output.content)
                elif isinstance(raw_output, str):
                    out_str = raw_output
                elif hasattr(raw_output, "update") and name != "write_todos":
                    msgs = raw_output.update.get("messages", []) if isinstance(raw_output.update, dict) else []
                    parts = [str(m.content) if hasattr(m, "content") else str(m) for m in msgs]
                    out_str = "\n".join(parts)
                else:
                    out_str = str(raw_output)

                yield f"data: {json.dumps({'type': 'tool', 'name': name, 'id': run_id, 'input': str(raw_input)[:STREAM_CONFIG['tool_input_truncate']], 'result': out_str})}\n\n"
                _fire_and_forget(_save_message(
                    thread_id, "tool", tool_name=name,
                    tool_args=json.dumps(raw_input, ensure_ascii=False, default=str) if raw_input else None,
                    tool_result=json.dumps(raw_output, ensure_ascii=False, default=str) if raw_output else None,
                    tool_status="done",
                ))

        # 保存 assistant 消息
        if current_text_parts:
            _fire_and_forget(_save_message(
                thread_id, "assistant", "".join(current_text_parts),
                thinking_content="".join(current_thinking_parts),
            ))

        # 检查 interrupt
        try:
            graph_state = await agent.aget_state({"configurable": config["configurable"]})
            if graph_state and graph_state.next:
                for task in (graph_state.tasks or []):
                    for interrupt_ in (task.interrupts or []):
                        val = interrupt_.value if hasattr(interrupt_, 'value') else interrupt_
                        if isinstance(val, dict):
                            for ar in val.get("action_requests", []):
                                if ar.get("name") == "ask_user":
                                    q = (ar.get("args") or {}).get("question", "")
                                    if q:
                                        yield f"data: {json.dumps({'type': 'interrupt', 'question': q})}\n\n"
                                        return
                        elif isinstance(val, str):
                            yield f"data: {json.dumps({'type': 'interrupt', 'question': val})}\n\n"
                            return
        except Exception:
            pass

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("SSE 异常 thread_id=%s", thread_id)
        yield f"data: {json.dumps({'type': 'error', 'content': '服务器内部错误'})}\n\n"


@router.post("/{thread_id}/stream")
async def stream_endpoint(thread_id: str, request: FastAPIRequest):
    body: dict[str, Any] = await request.json()
    content: str | None = body.get("content")

    session = session_manager.get(thread_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    session_manager.update_last_active(thread_id)

    try:
        agent = agent_pool.get_agent(thread_id)
    except Exception as e:
        logger.exception("Agent 初始化失败 thread_id=%s", thread_id)
        raise HTTPException(status_code=500, detail=str(e))

    if content:
        _fire_and_forget(_save_message(thread_id, "user", content))

    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 50,
    }

    async def generate():
        if not content:
            while True:
                yield ": heartbeat\n\n"
                await asyncio.sleep(STREAM_CONFIG["keepalive_seconds"])
        async for chunk in _stream_events(agent, config, content, thread_id):
            yield chunk

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{thread_id}/resume")
async def resume_endpoint(thread_id: str, request: FastAPIRequest):
    body: dict[str, Any] = await request.json()
    resume_value: str = body.get("resume", "")

    if not resume_value:
        raise HTTPException(status_code=400, detail="resume 不能为空")

    session = session_manager.get(thread_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    try:
        agent = agent_pool.get_agent(thread_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    from langgraph.types import Command
    command = Command(resume={"decisions": [{"type": "respond", "message": resume_value}]})

    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 50,
    }

    async def generate_with_command():
        current_text_parts: list[str] = []
        pending_tools: dict[str, dict] = {}
        try:
            async for event in agent.astream_events(command, config=config, version="v2"):
                evt_type = event.get("event", "")
                evt_data = event.get("data", {})

                if evt_type == "on_chat_model_stream":
                    chunk = evt_data.get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        current_text_parts.append(chunk.content)
                        yield f"data: {json.dumps({'type': 'text', 'content': chunk.content})}\n\n"
                    reasoning = getattr(chunk, "response_metadata", {}).get("reasoning_content", "")
                    if reasoning:
                        yield f"data: {json.dumps({'type': 'thinking', 'content': reasoning})}\n\n"

                elif evt_type == "on_tool_start":
                    run_id = event.get("run_id", "")
                    pending_tools[run_id] = {
                        "name": event.get("name", ""),
                        "input": evt_data.get("input", {}),
                    }

                elif evt_type == "on_tool_end":
                    run_id = event.get("run_id", "")
                    tool = pending_tools.pop(run_id, {})
                    name = tool.get("name", event.get("name", ""))
                    raw_input = tool.get("input", {})
                    raw_output = evt_data.get("output", {})
                    out_str = str(raw_output.content) if hasattr(raw_output, "content") else str(raw_output)
                    yield f"data: {json.dumps({'type': 'tool', 'name': name, 'id': run_id, 'input': str(raw_input)[:STREAM_CONFIG['tool_input_truncate']], 'result': out_str})}\n\n"

            # 检查 interrupt
            try:
                graph_state = await agent.aget_state({"configurable": {"thread_id": thread_id}})
                if graph_state and graph_state.next:
                    for task in (graph_state.tasks or []):
                        for interrupt_ in (task.interrupts or []):
                            val = interrupt_.value if hasattr(interrupt_, 'value') else interrupt_
                            if isinstance(val, dict):
                                for ar in val.get("action_requests", []):
                                    if ar.get("name") == "ask_user":
                                        q = (ar.get("args") or {}).get("question", "")
                                        if q:
                                            yield f"data: {json.dumps({'type': 'interrupt', 'question': q})}\n\n"
                                            return
                            elif isinstance(val, str):
                                yield f"data: {json.dumps({'type': 'interrupt', 'question': val})}\n\n"
                                return
            except Exception:
                pass

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Resume SSE 异常 thread_id=%s", thread_id)
            yield f"data: {json.dumps({'type': 'error', 'content': '服务器内部错误'})}\n\n"

    return StreamingResponse(
        generate_with_command(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
