"""pytest fixtures for WebSocket handler and agent streaming tests (v3 API).

LangGraph v3 astream_events returns an AsyncGraphRunStream with projections:
  - stream.messages -> AsyncChatModelStream (per LLM call), with .text / .tool_calls
  - stream.subgraphs -> AsyncSubgraphRunStream handles, with .graph_name / .status / .messages
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# ToolCallChunk — mimics langchain_core.messages.tool.ToolCallChunk
# ---------------------------------------------------------------------------

class _MockToolCallChunk:
    """Minimal ToolCallChunk stand-in for v3 streaming tool call chunks.

    In real v3 API, ``AsyncChatModelStream.tool_calls`` yields ToolCallChunk
    objects with: name, args, id, index, type.
    """

    def __init__(
        self,
        name: str = "",
        args: dict[str, Any] | str = "",
        id: str = "",
        index: int = 0,
        type: str = "tool_call",
        completed: bool = False,
        output: Any = None,
        error: Any = None,
    ) -> None:
        self.name = name
        self.args = args  # dict in early chunks, str in later (accumulated)
        self.id = id
        self.index = index
        self.type = type
        # Extended fields for completed detection
        self.completed = completed
        self.output = output
        self.error = error


# ---------------------------------------------------------------------------
# AsyncChatModelStream mock — one per LLM call in the v3 stream
# ---------------------------------------------------------------------------

class _MockChatStream:
    """Mimics AsyncChatModelStream with .text and .tool_calls async iterators.

    Usage in test setup::

        chat_stream = _MockChatStream(
            texts=["Hello", " world"],
            tool_calls=[
                _MockToolCallChunk(name="read_file", args={"file_path": "/skills/test/SKILL.md"}, id="tc1"),
                _MockToolCallChunk(name="read_file", completed=True, output="skill content...", id="tc1"),
            ],
        )
    """

    def __init__(
        self,
        texts: list[str] | None = None,
        tool_calls: list[_MockToolCallChunk] | None = None,
    ) -> None:
        self._texts = texts or []
        self._tool_calls = tool_calls or []
        self.text = _AsyncIterMock(self._texts)
        self.tool_calls = _AsyncIterMock(self._tool_calls)


class _AsyncIterMock:
    """Async iterator wrapper around a list."""

    def __init__(self, items: list[Any]) -> None:
        self._items = list(items)

    def __aiter__(self) -> _AsyncIterMock:
        return self

    async def __anext__(self) -> Any:
        if not self._items:
            raise StopAsyncIteration
        return self._items.pop(0)


# ---------------------------------------------------------------------------
# AsyncSubgraphRunStream mock — one per subgraph invocation
# ---------------------------------------------------------------------------

class _MockSubgraphHandle:
    """Mimics AsyncSubgraphRunStream with .graph_name, .status, .messages.

    Usage::

        sub_handle = _MockSubgraphHandle(
            graph_name="data-analyst",
            status="completed",
            chat_streams=[_MockChatStream(texts=["Analysis result..."])],
        )
    """

    def __init__(
        self,
        graph_name: str = "data-analyst",
        status: str = "started",
        chat_streams: list[_MockChatStream] | None = None,
    ) -> None:
        self.graph_name = graph_name
        self.status = status
        self.error: str | None = None
        self._chat_streams = chat_streams or []
        self.messages = _AsyncIterMock(self._chat_streams)


# ---------------------------------------------------------------------------
# AsyncGraphRunStream mock — the root stream returned by astream_events(v3)
# ---------------------------------------------------------------------------

class _MockStream:
    """Mimics AsyncGraphRunStream with .messages and .subgraphs projections."""

    def __init__(
        self,
        chat_streams: list[_MockChatStream] | None = None,
        subgraphs: list[_MockSubgraphHandle] | None = None,
    ) -> None:
        self._chat_streams = chat_streams or []
        self._subgraphs = subgraphs or []
        self.messages = _AsyncIterMock(list(self._chat_streams))
        self.subgraphs = _AsyncIterMock(list(self._subgraphs))

    # For lifecycle events if needed
    lifecycle = _AsyncIterMock([])


# ---------------------------------------------------------------------------
# mock_websocket — simple WebSocket stand-in for handler tests
# ---------------------------------------------------------------------------

class _MockWebSocket:
    """Minimal WebSocket fake with ``send_json`` and ``receive_text``."""

    def __init__(self) -> None:
        self.sent: list[Any] = []
        self._incoming: list[str] = []
        self._closed: bool = False

    async def accept(self) -> None:
        pass

    async def send_json(self, data: Any) -> None:
        self.sent.append(data)

    async def receive_text(self) -> str:
        if not self._incoming:
            raise RuntimeError("MockWebSocket has no queued incoming messages")
        return self._incoming.pop(0)

    async def receive_json(self) -> Any:
        import json
        text = await self.receive_text()
        return json.loads(text)

    def enqueue_text(self, text: str) -> None:
        self._incoming.append(text)

    def enqueue_json(self, data: Any) -> None:
        import json
        self._incoming.append(json.dumps(data))

    async def close(self) -> None:
        self._closed = True

    @property
    def closed(self) -> bool:
        return self._closed


@pytest.fixture
def mock_websocket() -> _MockWebSocket:
    """Return a fake WebSocket with send_json / receive_text methods."""
    return _MockWebSocket()


# ---------------------------------------------------------------------------
# Fixture: build a mock stream with the given projections
# ---------------------------------------------------------------------------

@pytest.fixture
def build_mock_stream():
    """Factory fixture: returns a helper to construct _MockStream instances."""

    def _build(
        texts: list[str] | None = None,
        tool_calls: list[_MockToolCallChunk] | None = None,
        subgraphs: list[_MockSubgraphHandle] | None = None,
    ) -> _MockStream:
        chat_streams: list[_MockChatStream] = []
        if texts is not None or tool_calls is not None:
            chat_streams.append(_MockChatStream(texts=texts, tool_calls=tool_calls))
        return _MockStream(chat_streams=chat_streams, subgraphs=subgraphs)

    return _build


# ---------------------------------------------------------------------------
# Fixture: patch agent_pool, session_manager, worktree_manager, os.path
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_agent(mock_websocket, build_mock_stream):
    """Patch agent_pool.get_agent to return a mock agent with v3 astream_events.

    Returns the mock_stream and agent for test inspection.
    """
    mock_stream = build_mock_stream(
        texts=["Hello from coordinator"],
        tool_calls=[
            _MockToolCallChunk(name="read_file", args={"file_path": "/data.csv"}, id="tc1"),
            _MockToolCallChunk(name="read_file", completed=True, output="csv content...", id="tc1"),
        ],
    )
    mock_agent = MagicMock()
    mock_agent.astream_events = AsyncMock(return_value=mock_stream)

    with (
        patch("ws_handler.agent_pool.get_agent", return_value=mock_agent),
        patch("ws_handler.session_manager.get", return_value={
            "session_id": "test-session",
            "title": "Test",
            "worktree_path": "sandboxes/test-session",
            "status": "active",
        }),
        patch("ws_handler.session_manager.update_last_active"),
        patch("ws_handler.worktree_manager.get_file_tree", return_value=[]),
        patch("ws_handler.os.path.exists", return_value=False),  # no history file
    ):
        yield mock_stream, mock_agent
