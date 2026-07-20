# backend/protocol_types.py
"""
Protocol v2 (Agent Streaming Protocol) 类型系统

基于 LangSmith Agent Streaming Protocol v2 规范实现的 Pydantic v2 模型。
定义了协议中所有的 SSE 事件类型、请求/响应结构及辅助函数。

参考规范:
  - https://docs.langchain.com/langsmith/agent-server-api/streaming/protocol-v2-event-stream-sse
  - https://github.com/langchain-ai/agent-protocol/blob/main/streaming/protocol.cddl

概览:
  ProtocolEventStreamRequest  → 客户端发起的 SSE 订阅请求
  ProtocolEvent               → 服务端推送的 SSE 事件
  ProtocolCommand             → 客户端发往服务端的命令
  ProtocolSuccess             → 命令执行成功响应
  ProtocolError               → 命令执行失败响应

  通道数据子类型:
    MessagesChannel  - MessageStartData, ContentBlockStartData,
                       ContentBlockDeltaData, ContentBlockFinishData,
                       MessageFinishData
    ToolsChannel     - ToolStartedData, ToolFinishedData
    LifecycleChannel - LifecycleStartedData, LifecycleRunningData,
                       LifecycleCompletedData, LifecycleFailedData,
                       LifecycleInterruptedData
"""

from __future__ import annotations

import time
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# ── 基础类型 ──────────────────────────────────────────────

# 预定义通道名称字面量
KnownChannel = Literal[
    "values",
    "updates",
    "messages",
    "tools",
    "lifecycle",
    "input",
    "tasks",
    "custom",
]
"""预定义的协议通道名称集合"""

ProtocolChannel = Annotated[
    str,
    StringConstraints(
        pattern=r'^(values|updates|messages|tools|lifecycle|input|tasks|checkpoints|custom|custom:[a-zA-Z0-9_-]+)$',
    ),
]
"""协议通道名称。可以是预定义通道 (values/updates/messages/tools/lifecycle/input/tasks/checkpoints/custom)
或自定义通道 (custom:<prefix>)"""

ProtocolNamespace = list[str]
"""协议命名空间，例如 ["agent", "llm"] 或 ["agent", "tools"]"""


# ── 事件流请求 ────────────────────────────────────────────


class ProtocolEventStreamRequest(BaseModel):
    """SSE 事件流的初始化请求体

    客户端通过此请求订阅感兴趣的事件通道和命名空间。
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    channels: list[ProtocolChannel] = Field(
        min_length=1,
        description="订阅的通道列表，至少需要一个通道",
    )
    namespaces: list[ProtocolNamespace] | None = Field(
        default=None,
        description="过滤的命名空间列表，None 表示所有命名空间",
    )
    depth: int | None = Field(
        default=None,
        ge=0,
        description="历史事件回溯深度，None 表示不回溯",
    )
    since: int | None = Field(
        default=None,
        ge=0,
        description="从指定时间戳（毫秒）之后的事件开始接收",
    )


# ── 事件参数 ──────────────────────────────────────────────


class EventParams(BaseModel):
    """ProtocolEvent 的参数部分

    描述事件的元数据：所属命名空间、发生时间、关联节点及具体数据。
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    namespace: list[str] = Field(
        description="事件所属命名空间路径",
    )
    timestamp: int = Field(
        ge=0,
        description="事件时间戳（毫秒）",
    )
    node: str | None = Field(
        default=None,
        description="关联的节点名称（如 langgraph 节点名）",
    )
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="事件的具体负载数据",
    )


# ── 事件主体 ──────────────────────────────────────────────


class ProtocolEvent(BaseModel):
    """SSE 协议事件

    服务端推送的基础事件单元。type 固定为 "event"，
    通过 method 区分事件类型，params 承载具体数据。
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["event"] = "event"
    event_id: str | None = Field(
        default=None,
        alias="event_id",
        description="事件唯一标识，用于去重",
    )
    seq: int | None = Field(
        default=None,
        ge=0,
        description="序列号，用于有序重放",
    )
    method: str = Field(
        description="事件方法名，如 metadata / messages/update",
    )
    params: EventParams = Field(
        description="事件参数",
    )


# ── Messages 通道子类型 ───────────────────────────────────


class MessageStartData(BaseModel):
    """messages 通道: message-start 事件

    表示一条新消息开始生成，包含角色和消息 ID。
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    event: Literal["message-start"]
    role: str = Field(description="消息角色，如 assistant / user")
    id: str = Field(description="消息唯一标识")


class ContentBlockStartData(BaseModel):
    """messages 通道: content-block-start 事件

    表示消息中的一个内容块开始生成，包含块索引和具体内容块定义。
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    event: Literal["content-block-start"]
    index: int = Field(ge=0, description="内容块在消息中的索引")
    content_block: dict[str, Any] = Field(description="内容块定义（如文本块、工具调用块）")


class ContentBlockDeltaData(BaseModel):
    """messages 通道: content-block-delta 事件

    表示消息中的一个内容块增量数据（流式文本片段）。
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    event: Literal["content-block-delta"]
    index: int = Field(ge=0, description="内容块在消息中的索引")
    delta: dict[str, Any] = Field(description="增量数据（如文本片段）")


class ContentBlockFinishData(BaseModel):
    """messages 通道: content-block-finish 事件

    表示消息中的一个内容块已完成生成。
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    event: Literal["content-block-finish"]
    index: int = Field(ge=0, description="内容块在消息中的索引")
    content_block: dict[str, Any] | None = Field(
        default=None,
        description="完成后的完整内容块（可选）",
    )


class MessageFinishData(BaseModel):
    """messages 通道: message-finish 事件

    表示整条消息生成完成，附带 token 用量统计。
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    event: Literal["message-finish"]
    usage: dict[str, Any] | None = Field(
        default=None,
        description="Token 用量统计（如 input_tokens / output_tokens）",
    )


# ── Tools 通道子类型 ──────────────────────────────────────


class ToolStartedData(BaseModel):
    """tools 通道: tool-started 事件

    表示一个工具开始执行。
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    event: Literal["tool-started"]
    tool_call_id: str = Field(description="工具调用唯一标识")
    tool_name: str = Field(description="工具名称")
    input: dict[str, Any] | None = Field(
        default=None,
        description="工具调用输入参数",
    )


class ToolFinishedData(BaseModel):
    """tools 通道: tool-finished 事件

    表示一个工具执行完成。
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    event: Literal["tool-finished"]
    tool_call_id: str = Field(description="工具调用唯一标识")
    tool_name: str = Field(description="工具名称")
    output: dict[str, Any] = Field(description="工具执行输出结果")


# ── Lifecycle 通道子类型 ──────────────────────────────────


class LifecycleStartedData(BaseModel):
    """lifecycle 通道: started 事件

    表示一个 graph 运行开始。
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    event: Literal["started"]
    graph_name: str | None = Field(
        default=None,
        description="Graph 名称",
    )
    cause: dict[str, Any] | None = Field(
        default=None,
        description="触发原因（如父级事件的上下文）",
    )


class LifecycleRunningData(BaseModel):
    """lifecycle 通道: running 事件

    表示一个 graph 正在运行中。
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    event: Literal["running"]
    graph_name: str = Field(description="Graph 名称")


class LifecycleCompletedData(BaseModel):
    """lifecycle 通道: completed 事件

    表示一个 graph 运行完成。
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    event: Literal["completed"]
    graph_name: str | None = Field(
        default=None,
        description="Graph 名称",
    )
    checkpoint: dict[str, Any] | None = Field(
        default=None,
        description="完成时的检查点快照",
    )


class LifecycleFailedData(BaseModel):
    """lifecycle 通道: failed 事件

    表示一个 graph 运行失败。
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    event: Literal["failed"]
    graph_name: str | None = Field(
        default=None,
        description="Graph 名称",
    )
    error: str = Field(description="错误描述")


class LifecycleInterruptedData(BaseModel):
    """lifecycle 通道: interrupted 事件

    表示一个 graph 运行被中断。
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    event: Literal["interrupted"]
    graph_name: str | None = Field(
        default=None,
        description="Graph 名称",
    )


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


# ── 辅助函数 ──────────────────────────────────────────────


def make_event(
    method: str,
    namespace: list[str],
    data: dict[str, Any],
    seq: int | None = None,
) -> ProtocolEvent:
    """构造一个 ProtocolEvent。

    Args:
        method: 事件方法名，如 "metadata" / "messages/update"
        namespace: 事件所属的命名空间
        data: 事件的具体负载数据
        seq: 可选的序列号，用于有序重放或去重

    Returns:
        构造完成的 ProtocolEvent，timestamp 自动设为当前时间（毫秒）
    """
    return ProtocolEvent(
        type="event",
        seq=seq,
        method=method,
        params=EventParams(
            namespace=namespace,
            timestamp=int(time.time() * 1000),
            data=data,
        ),
    )


def make_command(
    id: int,
    method: str,
    params: dict[str, Any] | None = None,
) -> ProtocolCommand:
    """构造一个 ProtocolCommand。

    Args:
        id: 命令唯一标识
        method: 命令方法名
        params: 命令参数，默认为空字典

    Returns:
        构造完成的 ProtocolCommand 实例
    """
    return ProtocolCommand(
        id=id,
        method=method,
        params=params or {},
    )
