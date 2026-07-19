"""Tests for SessionEventBuffer — per-session event ring buffer."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from backend.event_buffer import SessionEventBuffer
from backend.protocol_types import EventParams, ProtocolEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(data: dict[str, Any] | None = None) -> ProtocolEvent:
    """Build a minimal frozen ProtocolEvent for buffer tests."""
    return ProtocolEvent(
        type="event",
        method="test/event",
        params=EventParams(
            namespace=["test"],
            timestamp=1000,
            data=data or {},
        ),
    )


# ---------------------------------------------------------------------------
# add + replay
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_and_replay() -> None:
    """Add 3 events, replay from seq 0, verify all returned in order."""
    buf = SessionEventBuffer(max_size=500)
    tid = "thread-1"

    seq1 = await buf.add(tid, _make_event({"msg": "first"}))
    seq2 = await buf.add(tid, _make_event({"msg": "second"}))
    seq3 = await buf.add(tid, _make_event({"msg": "third"}))

    assert seq1 == 1
    assert seq2 == 2
    assert seq3 == 3

    events = await buf.replay_since(tid, 0)
    assert len(events) == 3
    assert [e.seq for e in events] == [1, 2, 3]
    assert [e.params.data["msg"] for e in events] == ["first", "second", "third"]


# ---------------------------------------------------------------------------
# replay filter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_replay_no_events_before_given_seq() -> None:
    """Replay from high seq returns empty; unknown thread returns empty."""
    buf = SessionEventBuffer(max_size=500)
    tid = "thread-2"

    await buf.add(tid, _make_event())
    await buf.add(tid, _make_event())
    await buf.add(tid, _make_event())

    # Replay past the latest seq
    events = await buf.replay_since(tid, 3)
    assert events == []

    # Replay from a very high seq
    events = await buf.replay_since(tid, 99)
    assert events == []

    # Unknown thread
    events = await buf.replay_since("unknown", 0)
    assert events == []


# ---------------------------------------------------------------------------
# ring-buffer eviction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_max_size_eviction() -> None:
    """Add more than max_size events; verify buffer is capped and seqs are contiguous."""
    max_size = 20
    extra = 10
    total = max_size + extra
    buf = SessionEventBuffer(max_size=max_size)
    tid = "thread-3"

    for i in range(total):
        await buf.add(tid, _make_event({"i": i}))

    assert buf.get_latest_seq(tid) == total

    events = await buf.replay_since(tid, 0)
    assert len(events) == max_size, f"Expected {max_size} events, got {len(events)}"

    # The oldest 'extra' events should have been evicted
    first_seq = events[0].seq
    assert first_seq == extra + 1, f"Expected first seq {extra + 1}, got {first_seq}"

    # Seqs are contiguous
    seqs = [e.seq for e in events]
    assert seqs == list(range(extra + 1, total + 1))


# ---------------------------------------------------------------------------
# concurrency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_adds() -> None:
    """10 concurrent add() calls — no data loss, all seqs 1..10 present."""
    buf = SessionEventBuffer(max_size=500)
    tid = "thread-4"
    concurrency = 10

    async def add_one(i: int) -> int:
        return await buf.add(tid, _make_event({"i": i}))

    results = await asyncio.gather(*[add_one(i) for i in range(concurrency)])

    # Every add returned a unique seq
    assert sorted(results) == list(range(1, concurrency + 1))
    assert buf.get_latest_seq(tid) == concurrency

    events = await buf.replay_since(tid, 0)
    assert len(events) == concurrency

    seqs = sorted(e.seq for e in events if e.seq is not None)
    assert seqs == list(range(1, concurrency + 1))


# ---------------------------------------------------------------------------
# cleanup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remove_cleans_up() -> None:
    """After remove(), thread returns latest_seq=0 and replay is empty."""
    buf = SessionEventBuffer(max_size=500)
    tid = "thread-5"

    await buf.add(tid, _make_event({"idx": 1}))
    await buf.add(tid, _make_event({"idx": 2}))
    assert buf.get_latest_seq(tid) == 2

    buf.remove(tid)

    assert buf.get_latest_seq(tid) == 0

    events = await buf.replay_since(tid, 0)
    assert events == []
