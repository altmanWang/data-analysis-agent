# backend/models/protocol.py
"""Protocol v2 命令/响应类型 — 当前仅命令模式生效"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ── 命令与响应 ────────────────────────────────────────────


class ProtocolCommand(BaseModel):
    """客户端发往服务器的命令

    类似于 JSON-RPC 请求，通过 id 关联请求与响应。
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: int = Field(ge=0, description="命令唯一标识，用于匹配响应")
    method: str = Field(description="命令方法名")
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="命令参数",
    )


class ProtocolSuccess(BaseModel):
    """命令执行成功的响应"""
    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["success"] = "success"
    id: int = Field(ge=0, description="对应命令的 id")
    result: dict[str, Any] = Field(description="执行结果")


class ProtocolError(BaseModel):
    """命令执行失败的响应"""
    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["error"] = "error"
    id: int = Field(ge=0, description="对应命令的 id")
    code: str = Field(description="错误码")
    message: str = Field(description="错误描述")
