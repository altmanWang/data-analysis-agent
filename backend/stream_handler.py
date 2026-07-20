# backend/stream_handler.py
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

from agent_pool import agent_pool
from db import get_connection
from session_manager import session_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/threads", tags=["stream"])

_KEEPALIVE = 15  # 心跳间隔（秒）
_db_executor = ThreadPoolExecutor(max_workers=4)


# ── 异步 DB 写入 ─────────────────────────────────────────────


def _save_message_sync(thread_id: str, role: str, content: str = "", **kwargs) -> None:
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO message_history (thread_id, role, content, tool_name, "
            "tool_args, tool_result, tool_status, extra) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (
                thread_id, role, content[:10000] if content else "",
                kwargs.get("tool_name"), kwargs.get("tool_args"),
                kwargs.get("tool_result"), kwargs.get("tool_status"),
                kwargs.get("extra"),
            ),
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        pass


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
        asyncio.create_task(_save_message(thread_id, "user", content))

    async def generate() -> AsyncIterator[str]:
        if not content:
            # 无 content → 纯心跳（供 hydration/keepalive）
            while True:
                yield ": heartbeat\n\n"
                await asyncio.sleep(_KEEPALIVE)

        current_text = ""
        tool_name_map: dict[str, str] = {}

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

                # ── LLM token ──
                if evt_type == "on_chat_model_stream":
                    chunk = evt_data.get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        text: str = chunk.content
                        current_text += text
                        yield f"data: {json.dumps({'type': 'text', 'content': text})}\n\n"

                # ── 工具开始 ──
                elif evt_type == "on_tool_start":
                    name: str = event.get("name", "")
                    run_id: str = event.get("run_id", "")
                    raw_input: dict = evt_data.get("input", {})
                    tool_name_map[run_id] = name
                    # 安全序列化
                    safe_input = {}
                    for k, v in raw_input.items():
                        if isinstance(v, (str, int, float, bool, list, dict, type(None))):
                            safe_input[k] = v
                        else:
                            safe_input[k] = str(v)[:500]
                    yield f"data: {json.dumps({'type': 'tool_start', 'name': name, 'id': run_id, 'input': safe_input})}\n\n"
                    asyncio.create_task(_save_message(
                        thread_id, "tool", tool_name=name,
                        tool_args=json.dumps(raw_input, ensure_ascii=False, default=str)[:5000] if raw_input else None,
                        tool_status="running",
                    ))

                # ── 工具结束 ──
                elif evt_type == "on_tool_end":
                    run_id = event.get("run_id", "")
                    name = tool_name_map.pop(run_id, event.get("name", ""))
                    raw_output: Any = evt_data.get("output", {})
                    if hasattr(raw_output, "content"):
                        out_str = str(raw_output.content)[:2000]
                    elif isinstance(raw_output, str):
                        out_str = raw_output[:2000]
                    else:
                        out_str = str(raw_output)[:2000]
                    yield f"data: {json.dumps({'type': 'tool_end', 'name': name, 'id': run_id, 'output': out_str})}\n\n"
                    asyncio.create_task(_save_message(
                        thread_id, "tool", tool_name=name,
                        tool_result=json.dumps(raw_output, ensure_ascii=False, default=str)[:5000] if raw_output else None,
                        tool_status="done",
                    ))

            # 保存 assistant 消息
            if current_text:
                asyncio.create_task(_save_message(thread_id, "assistant", current_text))

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

            # 完成后保持连接（心跳），供 SDK 后续复用
            while True:
                yield ": heartbeat\n\n"
                await asyncio.sleep(_KEEPALIVE)

        except asyncio.CancelledError:
            # 客户端断开 — 正常
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
