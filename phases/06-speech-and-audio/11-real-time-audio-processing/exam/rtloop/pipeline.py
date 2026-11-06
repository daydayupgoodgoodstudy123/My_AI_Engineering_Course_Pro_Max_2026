"""Run the stages of the voice loop concurrently, joined by bounded queues."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class Stats:
    delivered: int = 0  # frames the sink took without raising
    dropped: int = 0  # frames the mic dropped from the full first queue
    errors: int = 0  # frames lost because a stage or the sink raised


async def run_pipeline(
    frames: AsyncIterator[Any],
    stages: list[Callable[[Any], Awaitable[Any]]],
    sink: Callable[[Any], Awaitable[None]],
    maxsize: int = 4,
) -> Stats:
    """Pass mic frames through the stages, in order, into the sink, and return the counts.

    One task reads the mic, one task runs each stage and one task feeds the sink. Neighbouring
    tasks are joined by queues that hold at most maxsize items.
    - The mic is real time and never waits. When the first queue is full, the oldest frame
      waiting in it is dropped and counted: stale audio is worth less than fresh audio.
    - Every later queue makes the task in front of it wait while the queue is full.
    - A stage or the sink that raises on a frame loses only that frame, counted as an error.
    - When the mic stream ends, every frame still on its way is delivered before returning.
    - If run_pipeline is cancelled (the caller hung up), every task it started is cancelled,
      and run_pipeline waits until all of them have finished, cleanup included, before the
      cancellation propagates.
    """
    raise NotImplementedError
