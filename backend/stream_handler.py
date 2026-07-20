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
            "INSERT INTO message_history (session_id, role, content, thinking_content, tool_name, "
            "tool_args, tool_result, tool_status) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (
                thread_id, role, content[:10000] if content else "",
                kwargs.get("thinking_content", "")[:50000],
                kwargs.get("tool_name"), kwargs.get("tool_args"),
                kwargs.get("tool_result"), kwargs.get("tool_status"),
            ),
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        logger.exception("保存消息失败 thread_id=%s role=%s", thread_id, role)


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
        current_thinking = ""
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
                        current_text += text
                        yield f"data: {json.dumps({'type': 'text', 'content': text})}\n\n"
                    # R1 等推理模型的 thinking（仅 reasoning_content 非空时推送）
                    reasoning = getattr(chunk, "response_metadata", {}).get("reasoning_content", "")
                    if reasoning:
                        current_thinking += reasoning
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

                    yield f"data: {json.dumps({'type': 'tool', 'name': name, 'id': run_id, 'input': str(raw_input)[:200], 'result': out_str})}\n\n"
                    asyncio.create_task(_save_message(
                        thread_id, "tool", tool_name=name,
                        tool_args=json.dumps(raw_input, ensure_ascii=False, default=str) if raw_input else None,
                        tool_result=json.dumps(raw_output, ensure_ascii=False, default=str) if raw_output else None,
                        tool_status="done",
                    ))

            # 保存 assistant 消息（含思考过程）
            if current_text:
                asyncio.create_task(_save_message(
                    thread_id, "assistant", current_text,
                    thinking_content=current_thinking,
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
