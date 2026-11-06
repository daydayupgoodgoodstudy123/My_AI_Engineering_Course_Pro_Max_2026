"""Raise and clear spoof alarms on a live call, from the detector's scores as they arrive."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def watch_scores(
    batches: AsyncIterator[list[tuple[float, float]]],
    raise_at: float = 0.75,
    clear_below: float = 0.5,
    half_life_s: float = 0.5,
    cooldown_s: float = 2.0,
) -> AsyncIterator[str]:
    """Turn a call's spoof scores into alarms, sending each event as soon as it is decided.

    batches yields lists of (t, score): t is stream time in seconds and strictly increases
    (otherwise ValueError), and score is the countermeasure model's spoof probability for the
    window that ends at t. A list may have any length, including zero.

    Scores are smoothed in stream time. The first score starts the average s; each later score
    moves s towards itself by a fraction 1 - 0.5 ** (dt / half_life_s), where dt is the time since
    the previous score. An alarm starts at the first score where s reaches raise_at, and clears at
    the first later score where s falls below clear_below. After an alarm clears at t, the next
    one can start at t + cooldown_s at the earliest. An alarm still open when the stream ends
    clears at the last score.

    Events are Server-Sent Events: "alarm" with data {"t": t, "score": s} when an alarm starts,
    and "clear" with data {"t": t, "peak": the highest s during the alarm} when it clears.
    """
    s: float | None = None
    last: float | None = None
    peak: float | None = None  # highest s of the open alarm; None while no alarm is open
    earliest = float("-inf")  # when the next alarm may start
    async for batch in batches:
        for t, score in batch:
            if last is not None and t <= last:
                raise ValueError(f"score times must increase: {t} came after {last}")
            s = score if s is None else s + (1.0 - 0.5 ** ((t - last) / half_life_s)) * (score - s)
            last = t
            if peak is None:
                if s >= raise_at and t >= earliest:
                    peak = s
                    yield sse("alarm", {"t": t, "score": s})
            elif s < clear_below:
                yield sse("clear", {"t": t, "peak": peak})
                peak = None
                earliest = t + cooldown_s
            else:
                peak = max(peak, s)
    if peak is not None:
        yield sse("clear", {"t": last, "peak": peak})
