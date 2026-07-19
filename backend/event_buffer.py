"""Per-session event ring buffer for Protocol v2 SSE replay.

Stores ProtocolEvent objects per thread_id in an evicting ring buffer.
Thread-safe via per-thread asyncio.Lock.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.protocol_types import ProtocolEvent


class SessionEventBuffer:
    """Per-session ring buffer for Protocol v2 event replay.

    Stores up to *max_size* events per thread. When full, the oldest events are
    evicted (FIFO).  Thread-safe via ``asyncio.Lock`` per ``thread_id``.

    Each event is assigned a monotonically increasing sequence number (1‑based)
    scoped to its thread.  The buffer preserves insertion order.
    """

    def __init__(self, max_size: int = 500) -> None:
        if max_size < 1:
            raise ValueError("max_size must be >= 1")
        self._max_size = max_size
        self._buffers: dict[str, list[ProtocolEvent]] = {}
        self._seq_counters: dict[str, int] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_lock(self, thread_id: str) -> asyncio.Lock:
        if thread_id not in self._locks:
            self._locks[thread_id] = asyncio.Lock()
        return self._locks[thread_id]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def add(self, thread_id: str, event: ProtocolEvent) -> int:
        """Add *event* to the buffer for *thread_id*.

        Returns the assigned 1‑based sequence number.

        The event is stored with its ``seq`` field set to the returned value.
        If the buffer is at capacity the oldest event is evicted first.
        """
        async with self._get_lock(thread_id):
            seq = self._seq_counters.get(thread_id, 0) + 1
            self._seq_counters[thread_id] = seq

            # Copy the event with the assigned seq so the stored event
            # carries the authoritative sequence number.
            stored = event.model_copy(update={"seq": seq})

            buf = self._buffers.get(thread_id)
            if buf is None:
                self._buffers[thread_id] = [stored]
            else:
                buf.append(stored)
                if len(buf) > self._max_size:
                    # Evict oldest — pop from front
                    del buf[0]

            return seq

    async def replay_since(self, thread_id: str, since_seq: int) -> list[ProtocolEvent]:
        """Return all events for *thread_id* with ``seq > since_seq``.

        Returns an empty list when *thread_id* is unknown.
        Events are returned in insertion order.
        """
        buf = self._buffers.get(thread_id)
        if not buf:
            return []

        # Since the buffer is ordered and seq is monotonically increasing,
        # we can binary search for the first event with seq > since_seq.
        # For small buffers a linear scan is fine; these typically stay << 500.
        return [ev for ev in buf if ev.seq is not None and ev.seq > since_seq]

    def get_latest_seq(self, thread_id: str) -> int:
        """Return the latest sequence number for *thread_id*, or ``0`` if unknown."""
        return self._seq_counters.get(thread_id, 0)

    def remove(self, thread_id: str) -> None:
        """Remove all state for *thread_id*.

        Safe to call multiple times; no-op if the thread is unknown.
        """
        self._buffers.pop(thread_id, None)
        self._seq_counters.pop(thread_id, None)
        self._locks.pop(thread_id, None)
