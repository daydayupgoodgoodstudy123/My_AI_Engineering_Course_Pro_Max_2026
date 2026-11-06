"""Watch a live duplex session: its uplink and downlink, merged frame by frame."""
from __future__ import annotations

import json
from collections import deque
from collections.abc import AsyncIterator

from .mimi import FRAME_MS


async def timeline(
    uplink: AsyncIterator[list[dict]],
    downlink: AsyncIterator[list[dict]],
) -> AsyncIterator[str]:
    """Merge the two directions of a session into one NDJSON line per frame, as packets arrive.

    Each direction delivers bursts (lists) of packets {"frame": t, "voiced": bool}. The model
    sends a packet every 80 ms like the user does, silent frames included. Within a direction
    frame numbers only go up (ValueError otherwise), but a frame can be missing: a lost packet.

    The line for frame t is {"frame": t, "ms": t * 80, "user": ..., "model": ..., "overlap": ...,
    "barge_in": ...}. user and model are that side's voiced flag, or null if it never delivered
    frame t. overlap means both are voiced; barge_in means an overlap the user started: the user
    was not voiced in frame t - 1 (null counts as not voiced). Lines run from frame 0 to the last
    frame either side delivered, and frame t's line goes out as soon as each side has delivered
    frame t, moved past it, or ended.
    """
    user_side, model_side = _Side(uplink), _Side(downlink)
    t = 0
    user_before = False
    while True:
        user = await user_side.take(t)
        model = await model_side.take(t)
        if user is None and model is None and user_side.exhausted() and model_side.exhausted():
            return
        overlap = user is True and model is True
        line = {
            "frame": t,
            "ms": t * FRAME_MS,
            "user": user,
            "model": model,
            "overlap": overlap,
            "barge_in": overlap and not user_before,
        }
        yield json.dumps(line) + "\n"
        user_before = user is True
        t += 1


class _Side:
    """One direction of the session, read one burst at a time, only when needed."""

    def __init__(self, bursts: AsyncIterator[list[dict]]) -> None:
        self._bursts = bursts.__aiter__()
        self._pending: deque[dict] = deque()
        self._last = -1
        self._ended = False

    async def take(self, t: int) -> bool | None:
        """This side's voiced flag for frame t, or None if it never delivers frame t."""
        while not self._pending and not self._ended:
            try:
                burst = await self._bursts.__anext__()
            except StopAsyncIteration:
                self._ended = True
                break
            for packet in burst:
                if packet["frame"] <= self._last:
                    raise ValueError(f"frame {packet['frame']} arrived after frame {self._last}")
                self._last = packet["frame"]
                self._pending.append(packet)
        if self._pending and self._pending[0]["frame"] == t:
            return self._pending.popleft()["voiced"]
        return None

    def exhausted(self) -> bool:
        return self._ended and not self._pending
