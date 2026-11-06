"""Tag a live audio stream window by window."""
from __future__ import annotations

from collections.abc import AsyncIterator, Callable


async def stream_labels(
    chunks: AsyncIterator[list[float]],
    sample_rate: int,
    label_window: Callable[[list[float]], str],
    window_s: float = 0.5,
    hop_s: float = 0.25,
) -> AsyncIterator[str]:
    """Label overlapping windows of a stream as soon as each window is complete.

    Chunks may have any size. Emit one JSON object per window, newline-delimited:
    {"start": seconds, "end": seconds, "label": label_window(window_samples)}.
    """
    raise NotImplementedError
