"""Send a live generation to the player bar by bar, as Server-Sent Events."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator


async def stream_bars(tokens: AsyncIterator[str], steps_per_bar: int = 16) -> AsyncIterator[str]:
    """Group a generator's tokens into bars and send each bar as soon as it is complete.

    Tokens: "bar" opens the next bar (the stream starts with one), "pos:<step>" moves to a
    sixteenth step of the current bar (each bar starts at step 0), and "note:<pitch>:<steps>"
    plays a note there for that many steps. A bar is complete when the next "bar" arrives or
    the stream ends. A token that does not fit raises ValueError.

    Each bar goes out as one Server-Sent Event, "data: <json>" plus a blank line, with
    {"bar": index, "notes": [{"pitch": p, "step": s, "steps": n, "tied": bool}, ...]}.
    A note that rings past the bar line is cut there and continues at step 0 of the next
    bars as tied notes, which come before the bar's new notes. When the stream ends, bars
    keep going out until every note has finished.
    """
    bar = -1
    step = 0
    notes: list[dict] = []
    ringing: list[tuple[int, int]] = []  # (pitch, steps left after the current bar), in start order
    async for token in tokens:
        kind, *args = token.split(":")
        if kind == "bar":
            if bar >= 0:
                yield _event(bar, notes)
            bar += 1
            step = 0
            notes, ringing = _carry(ringing, steps_per_bar)
            continue
        if bar < 0:
            raise ValueError(f"{token!r} before the first bar")
        if kind == "pos" and len(args) == 1 and 0 <= int(args[0]) < steps_per_bar:
            step = int(args[0])
        elif kind == "note" and len(args) == 2 and int(args[1]) > 0:
            pitch, steps = int(args[0]), int(args[1])
            room = steps_per_bar - step
            notes.append({"pitch": pitch, "step": step, "steps": min(steps, room), "tied": False})
            if steps > room:
                ringing.append((pitch, steps - room))
        else:
            raise ValueError(f"unexpected token {token!r}")
    if bar < 0:
        return
    yield _event(bar, notes)
    while ringing:
        bar += 1
        notes, ringing = _carry(ringing, steps_per_bar)
        yield _event(bar, notes)


def _carry(ringing: list[tuple[int, int]], steps_per_bar: int) -> tuple[list[dict], list[tuple[int, int]]]:
    """Tied notes that open the next bar, and what still rings after it."""
    tied = [{"pitch": p, "step": 0, "steps": min(left, steps_per_bar), "tied": True} for p, left in ringing]
    still = [(p, left - steps_per_bar) for p, left in ringing if left > steps_per_bar]
    return tied, still


def _event(bar: int, notes: list[dict]) -> str:
    return "data: " + json.dumps({"bar": bar, "notes": notes}) + "\n\n"
