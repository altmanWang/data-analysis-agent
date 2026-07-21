# backend/api/stream.py
"""简单 SSE 流式端点 — agent.astream_events(v2) → SSE 帧

实现 POST /api/threads/{thread_id}/stream:
  1. 接受 content 字段触发 agent 运行（无 content 时仅心跳）
  2. agent.astream_events(v2) 事件直接映射为简单 JSON → SSE
  3. 异步保存消息到 DB
  4. 客户端断开时自动取消
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
    """创建后台任务并记录异常，防止静默丢失。"""
    task = asyncio.create_task(coro)
    task.add_done_callback(lambda t: logger.exception("后台任务异常", exc_info=t.exception()) if t.exception() else None)
    return task


# ── 异步 DB 写入 ─────────────────────────────────────────────


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


# ── SSE 端点 ─────────────────────────────────────────────────


@router.post("/{thread_id}/stream")
async def stream_endpoint(thread_id: str, request: FastAPIRequest):
    body: dict[str, Any] = await request.json()
    content: str | None = body.get("content")

    # 验证会话
    session = session_manager.get(thread_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    session_manager.update_last_active(thread_id)

    # 获取 agent
    try:
        agent = agent_pool.get_agent(thread_id)
    except Exception as e:
        logger.exception("Agent 初始化失败 thread_id=%s", thread_id)
        raise HTTPException(status_code=500, detail=str(e))

    # 保存用户消息
    if content:
        _fire_and_forget(_save_message(thread_id, "user", content))

    async def generate() -> AsyncIterator[str]:
        if not content:
            # 无 content → 纯心跳（供 hydration/keepalive）
            while True:
                yield ": heartbeat\n\n"
                await asyncio.sleep(STREAM_CONFIG["keepalive_seconds"])

        current_text_parts: list[str] = []
        current_thinking_parts: list[str] = []
        pending_tools: dict[str, dict] = {}  # run_id → {name, input}

        try:
            async for event in agent.astream_events(
                {"messages": [{"role": "user", "content": content}]} if content else {},
                config={
                    "configurable": {"thread_id": thread_id},
                    "recursion_limit": 50,
                },
                version="v2",
            ):
                evt_type: str = event.get("event", "")
                evt_data: dict[str, Any] = event.get("data", {})

                # ── LLM 输出文本 ──
                if evt_type == "on_chat_model_stream":
                    chunk = evt_data.get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        text: str = chunk.content
                        current_text_parts.append(text)
                        yield f"data: {json.dumps({'type': 'text', 'content': text})}\n\n"
                    # R1 等推理模型的 thinking（仅 reasoning_content 非空时推送）
                    reasoning = getattr(chunk, "response_metadata", {}).get("reasoning_content", "")
                    if reasoning:
                        current_thinking_parts.append(reasoning)
                        yield f"data: {json.dumps({'type': 'thinking', 'content': reasoning})}\n\n"

                # ── 工具开始（仅缓存，不推送）──
                elif evt_type == "on_tool_start":
                    run_id: str = event.get("run_id", "")
                    name: str = event.get("name", "")
                    pending_tools[run_id] = {
                        "name": name,
                        "input": evt_data.get("input", {}),
                    }

                # ── 工具结束（合并推送）──
                elif evt_type == "on_tool_end":
                    run_id = event.get("run_id", "")
                    tool = pending_tools.pop(run_id, {})
                    name = tool.get("name", event.get("name", ""))
                    raw_input = tool.get("input", {})
                    raw_output: Any = evt_data.get("output", {})

                    # 提取输出文本
                    if hasattr(raw_output, "content"):
                        out_str = str(raw_output.content)
                    elif isinstance(raw_output, str):
                        out_str = raw_output
                    elif hasattr(raw_output, "update") and name != "write_todos":
                        # Command 对象（如 task 子代理）：提取 messages 文本
                        msgs = raw_output.update.get("messages", []) if isinstance(raw_output.update, dict) else []
                        parts = []
                        for m in msgs:
                            if hasattr(m, "content"):
                                parts.append(str(m.content))
                            elif isinstance(m, str):
                                parts.append(m)
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

            # 保存 assistant 消息（含思考过程）
            if current_text_parts:
                _fire_and_forget(_save_message(
                    thread_id, "assistant", "".join(current_text_parts),
                    thinking_content="".join(current_thinking_parts),
                ))

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("SSE 异常 thread_id=%s", thread_id)
            yield f"data: {json.dumps({'type': 'error', 'content': '服务器内部错误'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
