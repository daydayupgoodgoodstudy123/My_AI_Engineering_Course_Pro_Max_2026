"""Send a live generation to the player bar by bar, as Server-Sent Events."""
from __future__ import annotations

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
    raise NotImplementedError
