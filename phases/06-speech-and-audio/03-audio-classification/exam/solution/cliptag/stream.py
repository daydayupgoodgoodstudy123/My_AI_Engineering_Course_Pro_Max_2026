"""Tag a live audio stream window by window."""
from __future__ import annotations

import json
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
    window = round(window_s * sample_rate)
    hop = round(hop_s * sample_rate)
    if window <= 0 or not 0 < hop <= window:
        raise ValueError("need 0 < hop <= window")
    buffer: list[float] = []
    start = 0  # stream index of buffer[0], counted in samples so times never drift
    async for chunk in chunks:
        buffer.extend(chunk)
        while len(buffer) >= window:
            event = {
                "start": start / sample_rate,
                "end": (start + window) / sample_rate,
                "label": label_window(buffer[:window]),
            }
            yield json.dumps(event) + "\n"
            del buffer[:hop]
            start += hop
