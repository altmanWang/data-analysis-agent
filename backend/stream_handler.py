# backend/stream_handler.py
"""Protocol v2 SSE 事件流端点 — 将 agent.astream_events(v2) 映射为 SSE 帧

实现 POST /api/threads/{thread_id}/stream 端点:
  1. 接受 ProtocolEventStreamRequest 订阅参数 (channels, namespaces, depth, since)
  2. 接受可选 content 字段触发 agent 运行
  3. 如果提供 since 参数，先重放缓冲区中的历史事件
  4. 后台运行 agent.astream_events(v2)，将 langgraph 事件映射为 Protocol v2 SSE 帧
  5. 支持 channels 过滤 (messages / tools / lifecycle) 和 namespace 前缀匹配
  6. 每 15s 发送 SSE heartbeat 保活
  7. 客户端断开时取消后台 agent 任务
  8. 异常时发送 lifecycle/failed 事件后关闭流
"""

from __future__ import annotations

import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, AsyncIterator

import httpx
from fastapi import APIRouter, Request as FastAPIRequest
from fastapi.responses import StreamingResponse

from agent_pool import agent_pool
from event_buffer import SessionEventBuffer
from protocol_types import (
    ProtocolEvent,
    ProtocolEventStreamRequest,
    ProtocolNamespace,
    make_event,
)
from session_manager import session_manager
from db import get_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/threads", tags=["stream"])

# 全局事件缓冲区 — 与 ws_handler 共享同一实例（未来 ws_handler 也应写入此缓冲区）
event_buffer = SessionEventBuffer(max_size=500)

# 可重试的网络层异常（LLM API 连接中断等）
_RETRYABLE_ERRORS = (
    httpx.RemoteProtocolError,
    httpx.ReadError,
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.ConnectTimeout,
)
_MAX_RETRIES = 2
_KEEPALIVE_INTERVAL = 15  # 秒
_db_executor = ThreadPoolExecutor(max_workers=4)  # 异步写库线程池


# ── 辅助函数 ────────────────────────────────────────────────


def _save_message_sync(thread_id: str, role: str, content: str = "", **kwargs) -> None:
    """同步写入 message_history 表（在独立线程中执行，不阻塞 SSE 主循环）"""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO message_history (thread_id, role, content, tool_name, tool_args, tool_result, tool_status, extra) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (
                thread_id,
                role,
                content[:10000] if content else "",
                kwargs.get("tool_name"),
                kwargs.get("tool_args"),
                kwargs.get("tool_result"),
                kwargs.get("tool_status"),
                kwargs.get("extra"),
            ),
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        pass  # 不阻塞流式传输


async def _save_message(thread_id: str, role: str, content: str = "", **kwargs) -> None:
    """异步保存消息 — 通过线程池执行，不阻塞 SSE 主循环"""
    loop = asyncio.get_running_loop()
    loop.run_in_executor(_db_executor, _save_message_sync, thread_id, role, content, **kwargs)


def format_sse(event: ProtocolEvent) -> str:
    """将 ProtocolEvent 格式化为 SSE 帧

    输出格式:
        id: {seq}\\n
        event: {method}\\n
        data: {json}\\n\\n

    其中 seq 仅在非 None 时输出，event 使用 ProtocolEvent.method。
    """
    lines: list[str] = []
    if event.seq is not None:
        lines.append(f"id: {event.seq}")
    lines.append(f"event: {event.method}")
    lines.append(f"data: {event.model_dump_json(by_alias=True)}")
    lines.append("")  # SSE 空白行分隔
    return "\n".join(lines) + "\n"


async def _emit(
    thread_id: str,
    method: str,
    namespace: list[str],
    data: dict[str, Any],
) -> ProtocolEvent:
    """构造 ProtocolEvent、写入缓冲区、返回带 seq 的事件副本"""
    evt = make_event(method=method, namespace=namespace, data=data, seq=None)
    seq = await event_buffer.add(thread_id, evt)
    return evt.model_copy(update={"seq": seq})


def _channel_subscribed(channel: str, subscribed: list[str]) -> bool:
    """检查通道是否在订阅列表中"""
    return channel in subscribed


def _namespace_ok(
    event_ns: list[str],
    filters: list[ProtocolNamespace] | None,
) -> bool:
    """检查事件命名空间是否匹配至少一个过滤器（前缀匹配）。

    None 过滤器表示放行所有命名空间。
    """
    if filters is None:
        return True
    for f in filters:
        if len(f) <= len(event_ns) and event_ns[: len(f)] == f:
            return True
    return False


def _extract_usage(metadata: dict[str, Any]) -> dict[str, Any]:
    """从 langgraph metadata 提取 token 用量统计"""
    usage: dict[str, Any] = {}
    for key in ("input_tokens", "output_tokens", "total_tokens"):
        if key in metadata:
            usage[key] = metadata[key]
    return usage


def _safe_serialize_input(raw: dict[str, Any]) -> dict[str, Any]:
    """将工具输入转为安全的可 JSON 序列化字典"""
    safe: dict[str, Any] = {}
    for k, v in raw.items():
        if isinstance(v, (str, int, float, bool, list, dict, type(None))):
            safe[k] = v
        else:
            safe[k] = str(v)[:500]
    return safe


def _safe_serialize_output(raw: Any) -> dict[str, Any]:
    """将工具输出转为安全的可 JSON 序列化字典"""
    if hasattr(raw, "content"):
        return {"content": str(raw.content)[:2000]}
    if isinstance(raw, str):
        return {"content": raw[:2000]}
    if isinstance(raw, dict):
        return raw
    return {"content": str(raw)[:2000]}


# ── SSE 端点 ────────────────────────────────────────────────


@router.post("/{thread_id}/stream")
@router.post("/{thread_id}/stream/events")  # @langchain/vue SDK 别名
async def stream_endpoint(thread_id: str, fastapi_request: FastAPIRequest):
    """Protocol v2 SSE 事件流

    接受 JSON body:
      - channels:     订阅的通道列表 (如 ["messages", "tools", "lifecycle"])
      - namespaces:   命名空间过滤 (可选, None=全部)
      - depth:        历史回溯深度 (可选)
      - since:        从指定 seq 之后重放缓冲区事件 (可选)
      - content:      用户输入内容 (可选, 提供时触发 agent 运行)

    返回: StreamingResponse (text/event-stream)
    """
    # ── 解析请求体 ──
    body: dict[str, Any] = await fastapi_request.json()
    sub_keys = {"channels", "namespaces", "depth", "since"}
    subscription = ProtocolEventStreamRequest(
        **{k: v for k, v in body.items() if k in sub_keys}
    )
    channels: list[str] = list(subscription.channels)
    namespaces: list[ProtocolNamespace] | None = subscription.namespaces
    since: int | None = subscription.since
    user_content: str | None = body.get("content")
    if user_content:
        asyncio.create_task(_save_message(thread_id, "user", user_content))

    # ── SSE 生成器 ──
    async def generate() -> AsyncIterator[str]:
        """异步生成器: yield SSE 帧"""
        # 告知客户端 SSE 重连间隔（毫秒），fetchEventSource 会据此恢复连接
        yield "retry: 3000\n\n"

        # ── 验证会话（走 SSE 帧而非 HTTP 异常，让前端 onerror 统一处理）──
        session = session_manager.get(thread_id)
        if not session:
            err_evt = ProtocolEvent(
                seq=None,
                method="error",
                params={"data": {"code": "SESSION_NOT_FOUND", "message": "会话不存在"}},
            )
            yield format_sse(err_evt)
            return
        session_manager.update_last_active(thread_id)

        try:
            agent = agent_pool.get_agent(thread_id)
        except Exception as e:
            logger.exception("Agent 初始化失败 thread_id=%s", thread_id)
            err_evt = ProtocolEvent(
                seq=None,
                method="error",
                params={"data": {"code": "AGENT_INIT_FAILED", "message": str(e)}},
            )
            yield format_sse(err_evt)
            return

        stream_task: asyncio.Task[None] | None = None
        event_queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue(maxsize=256)
        # 追踪每个 tool run_id 对应的 tool_name（on_tool_end 可能不含 name）
        tool_name_map: dict[str, str] = {}
        content_block_index = 0
        run_id = ""
        current_text = ""  # 累积 assistant 消息文本

        try:
            # ── Phase 1: 重放缓冲区历史事件 ──
            if since is not None:
                buffered = await event_buffer.replay_since(thread_id, since)
                for evt in buffered:
                    yield format_sse(evt)

            # ── Phase 2: 后台运行 agent ──
            async def _run_agent() -> None:
                """后台任务: agent.astream_events(v2) → 推入 event_queue"""
                stream_config = {
                    "configurable": {"thread_id": thread_id},
                    "recursion_limit": 50,
                }
                messages: list[dict[str, str]] = []
                if user_content:
                    messages = [{"role": "user", "content": user_content}]

                for attempt in range(_MAX_RETRIES + 1):
                    try:
                        async for event in agent.astream_events(
                            {"messages": messages},
                            config=stream_config,
                            version="v2",
                        ):
                            await event_queue.put(("event", event))
                        await event_queue.put(("done", None))
                        return
                    except _RETRYABLE_ERRORS as e:
                        if attempt < _MAX_RETRIES:
                            wait = 2**attempt
                            logger.warning(
                                "LLM 连接中断 thread_id=%s (attempt %d/%d): %s",
                                thread_id,
                                attempt + 1,
                                _MAX_RETRIES + 1,
                                e,
                            )
                            await asyncio.sleep(wait)
                        else:
                            await event_queue.put(("error", e))
                            return
                    except Exception as e:
                        await event_queue.put(("error", e))
                        return

            stream_task = asyncio.create_task(_run_agent(), name=f"agent-{thread_id}")

            # 内部辅助: 同时检查 channel 订阅 + namespace 过滤
            def _ok(channel: str, ns: list[str]) -> bool:
                return _channel_subscribed(channel, channels) and _namespace_ok(
                    ns, namespaces
                )

            # ── Phase 3: SSE 主循环 — 从队列消费并映射事件 ──
            while True:
                # 带超时的队列等待，超时时发送心跳
                try:
                    queue_item = await asyncio.wait_for(
                        event_queue.get(), timeout=_KEEPALIVE_INTERVAL
                    )
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
                    continue

                kind, payload = queue_item

                # ── 终止信号 ──
                if kind == "done":
                    if _ok("lifecycle", ["lifecycle"]):
                        evt = await _emit(
                            thread_id,
                            method="lifecycle/update",
                            namespace=["lifecycle"],
                            data={"event": "completed", "graph_name": "main"},
                        )
                        yield format_sse(evt)
                    break

                if kind == "error":
                    error_msg = (
                        str(payload) if not isinstance(payload, Exception)
                        else f"{type(payload).__name__}: {payload}"
                    )
                    logger.error(
                        "Agent 运行失败 thread_id=%s: %s", thread_id, error_msg
                    )
                    if _ok("lifecycle", ["lifecycle"]):
                        evt = await _emit(
                            thread_id,
                            method="lifecycle/update",
                            namespace=["lifecycle"],
                            data={
                                "event": "failed",
                                "graph_name": "main",
                                "error": error_msg,
                            },
                        )
                        yield format_sse(evt)
                    break

                # kind == "event" — 映射 langgraph 事件到 Protocol v2
                event: dict[str, Any] = payload
                evt_type: str = event.get("event", "")
                evt_data: dict[str, Any] = event.get("data", {})

                # ── on_chat_model_start → message-start + content-block-start ──
                if evt_type == "on_chat_model_start":
                    if not _ok("messages", ["messages"]):
                        continue
                    run_id = event.get("run_id", "")
                    content_block_index = 0

                    # message-start
                    evt = await _emit(
                        thread_id,
                        method="messages/update",
                        namespace=["messages"],
                        data={
                            "event": "message-start",
                            "role": "assistant",
                            "id": run_id,
                        },
                    )
                    yield format_sse(evt)

                    # content-block-start
                    evt = await _emit(
                        thread_id,
                        method="messages/update",
                        namespace=["messages"],
                        data={
                            "event": "content-block-start",
                            "index": content_block_index,
                            "content_block": {"type": "text"},
                        },
                    )
                    yield format_sse(evt)

                # ── on_chat_model_stream → content-block-delta ──
                elif evt_type == "on_chat_model_stream":
                    if not _ok("messages", ["messages"]):
                        continue
                    chunk = evt_data.get("chunk")
                    if chunk is None or not hasattr(chunk, "content"):
                        continue
                    text: str = chunk.content or ""
                    if not text:
                        continue
                    current_text += text
                    evt = await _emit(
                        thread_id,
                        method="messages/update",
                        namespace=["messages"],
                        data={
                            "event": "content-block-delta",
                            "index": content_block_index,
                            "delta": {"type": "text-delta", "text": text},
                        },
                    )
                    yield format_sse(evt)

                # ── on_chat_model_end → content-block-finish + message-finish ──
                elif evt_type == "on_chat_model_end":
                    if not _ok("messages", ["messages"]):
                        continue
                    output = evt_data.get("output", {})
                    usage_info: dict[str, Any] = {}
                    if hasattr(output, "usage_metadata") and output.usage_metadata:
                        usage_info = dict(output.usage_metadata)
                    elif hasattr(output, "response_metadata") and output.response_metadata:
                        usage_info = _extract_usage(output.response_metadata)

                    # content-block-finish
                    evt = await _emit(
                        thread_id,
                        method="messages/update",
                        namespace=["messages"],
                        data={
                            "event": "content-block-finish",
                            "index": content_block_index,
                        },
                    )
                    yield format_sse(evt)

                    # message-finish
                    evt = await _emit(
                        thread_id,
                        method="messages/update",
                        namespace=["messages"],
                        data={
                            "event": "message-finish",
                            "usage": usage_info if usage_info else None,
                        },
                    )
                    yield format_sse(evt)
                    asyncio.create_task(_save_message(thread_id, "assistant", current_text))
                    current_text = ""

                # ── on_tool_start → tool-started ──
                elif evt_type == "on_tool_start":
                    if not _ok("tools", ["tools"]):
                        continue
                    tool_run_id: str = event.get("run_id", "")
                    tool_name: str = event.get("name", "")
                    raw_input: dict[str, Any] = evt_data.get("input", {})
                    tool_name_map[tool_run_id] = tool_name
                    safe_input = _safe_serialize_input(raw_input)
                    logger.debug("tool-started: name=%s input_keys=%s safe_keys=%s",
                        tool_name, list(raw_input.keys()) if isinstance(raw_input, dict) else type(raw_input),
                        list(safe_input.keys()) if isinstance(safe_input, dict) else type(safe_input))

                    evt = await _emit(
                        thread_id,
                        method="tools/update",
                        namespace=["tools"],
                        data={
                            "event": "tool-started",
                            "tool_call_id": tool_run_id,
                            "tool_name": tool_name,
                            "input": safe_input,
                        },
                    )
                    yield format_sse(evt)
                    asyncio.create_task(_save_message(thread_id, "tool", tool_name=tool_name,
                        tool_args=json.dumps(raw_input, ensure_ascii=False, default=str)[:5000] if raw_input else None,
                        tool_status="running"))

                # ── on_tool_end → tool-finished ──
                elif evt_type == "on_tool_end":
                    if not _ok("tools", ["tools"]):
                        continue
                    tool_run_id = event.get("run_id", "")
                    tool_name = tool_name_map.pop(
                        tool_run_id, event.get("name", "")
                    )
                    raw_output: Any = evt_data.get("output", {})
                    safe_output = _safe_serialize_output(raw_output)
                    logger.debug("tool-finished: name=%s output_type=%s output_keys=%s",
                        tool_name, type(raw_output).__name__,
                        list(safe_output.keys()) if isinstance(safe_output, dict) else type(safe_output))
                    evt = await _emit(
                        thread_id,
                        method="tools/update",
                        namespace=["tools"],
                        data={
                            "event": "tool-finished",
                            "tool_call_id": tool_run_id,
                            "tool_name": tool_name,
                            "output": safe_output,
                        },
                    )
                    yield format_sse(evt)
                    asyncio.create_task(_save_message(thread_id, "tool", tool_name=tool_name,
                        tool_result=json.dumps(raw_output, ensure_ascii=False, default=str)[:5000] if raw_output else None,
                        tool_status="done"))

            # 正常完成 — 清除 task 引用
            stream_task = None

        except asyncio.CancelledError:
            # 客户端断开连接 → 取消后台 agent
            if stream_task and not stream_task.done():
                stream_task.cancel()
                try:
                    await stream_task
                except asyncio.CancelledError:
                    pass
            raise

        except Exception:
            logger.exception("SSE 流异常 thread_id=%s", thread_id)
            if _ok("lifecycle", ["lifecycle"]):
                try:
                    evt = await _emit(
                        thread_id,
                        method="lifecycle/update",
                        namespace=["lifecycle"],
                        data={
                            "event": "failed",
                            "graph_name": "main",
                            "error": "服务器内部错误",
                        },
                    )
                    yield format_sse(evt)
                except Exception:
                    pass
            raise

        finally:
            # 确保后台任务被清理
            if stream_task and not stream_task.done():
                stream_task.cancel()
                try:
                    await stream_task
                except (asyncio.CancelledError, Exception):
                    pass

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 nginx 代理缓冲
        },
    )
