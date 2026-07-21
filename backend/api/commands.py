# backend/api/commands.py
"""Protocol v2 命令端点 — 接收并分发客户端命令

实现 POST /api/threads/{thread_id}/commands 端点:
  1. 接受 ProtocolCommand 请求体 (id, method, params)
  2. 验证会话存在性
  3. 根据 method 路由到对应命令处理器:
     - run.start:      启动 agent 运行（实际流式输出通过 /stream SSE 端点）
     - input.respond:  响应用户输入（占位，完整实现待后续）
  4. 返回 ProtocolSuccess 或 ProtocolError
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from models.protocol import ProtocolCommand, ProtocolError, ProtocolSuccess
from services.session_manager import session_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/threads", tags=["commands"])


@router.post("/{thread_id}/commands")
async def handle_command(thread_id: str, command: ProtocolCommand) -> ProtocolSuccess | ProtocolError:
    """接收并处理 Protocol v2 命令

    Args:
        thread_id: 会话/线程 ID
        command:   协议命令 (id, method, params)

    Returns:
        ProtocolSuccess: 命令执行成功
        ProtocolError:   命令执行失败
    """
    # ── 验证会话 ──
    session = session_manager.get(thread_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    method: str = command.method
    params: dict[str, Any] = command.params

    # ── run.start: 启动 agent 运行 ──
    if method == "run.start":
        return _handle_run_start(thread_id, command.id, params)

    # ── input.respond: 响应用户输入 ──
    if method == "input.respond":
        return _handle_input_respond(thread_id, command.id, params)

    # ── 未知命令 ──
    logger.warning("未知命令 thread_id=%s method=%s", thread_id, method)
    return ProtocolError(
        type="error",
        id=command.id,
        code="unknown_command",
        message=f"未知命令: {method}",
    )


def _handle_run_start(thread_id: str, cmd_id: int, params: dict[str, Any]) -> ProtocolSuccess | ProtocolError:
    """处理 run.start 命令

    验证 params 包含 "input" 或 "messages"，更新会话最后活跃时间，
    返回成功状态。实际的流式运行由 /stream SSE 端点处理。

    Args:
        thread_id: 会话 ID
        cmd_id:    命令 ID
        params:    命令参数，需包含 "input" 或 "messages"

    Returns:
        ProtocolSuccess: 启动成功
        ProtocolError:   参数校验失败
    """
    if "input" not in params and "messages" not in params:
        return ProtocolError(
            type="error",
            id=cmd_id,
            code="invalid_params",
            message="run.start 需要 'input' 或 'messages' 参数",
        )

    session_manager.update_last_active(thread_id)

    return ProtocolSuccess(
        type="success",
        id=cmd_id,
        result={
            "thread_id": thread_id,
            "status": "started",
        },
    )


def _handle_input_respond(thread_id: str, cmd_id: int, params: dict[str, Any]) -> ProtocolSuccess | ProtocolError:
    """处理 input.respond 命令（占位实现）

    验证 params 包含 "interrupt_id" 和 "response"。
    完整实现（与 langgraph interrupt 处理交织）待后续补充。

    Args:
        thread_id: 会话 ID
        cmd_id:    命令 ID
        params:    命令参数，需包含 "interrupt_id" 和 "response"

    Returns:
        ProtocolSuccess: 接收成功
        ProtocolError:   参数校验失败
    """
    if "interrupt_id" not in params or "response" not in params:
        return ProtocolError(
            type="error",
            id=cmd_id,
            code="invalid_params",
            message="input.respond 需要 'interrupt_id' 和 'response' 参数",
        )

    session_manager.update_last_active(thread_id)

    return ProtocolSuccess(
        type="success",
        id=cmd_id,
        result={
            "thread_id": thread_id,
            "status": "accepted",
        },
    )
