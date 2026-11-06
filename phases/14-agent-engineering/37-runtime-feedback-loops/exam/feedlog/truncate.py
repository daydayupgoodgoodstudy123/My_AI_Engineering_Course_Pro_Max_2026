"""Deterministic head-and-tail truncation, so one record never blows the agent's token budget."""
from __future__ import annotations

HEAD_LINES = 5
TAIL_LINES = 30


def truncate_lines(text: str, head: int = HEAD_LINES, tail: int = TAIL_LINES) -> tuple[str, int]:
    """Keep the first head lines and the last tail lines of text.

    Lines end at "\\n" and nowhere else; a "\\r\\n" line keeps its "\\r". A "\\n" at the very end
    closes the last line and does not start another one.

    When text has more than head + tail lines, the lines between them are replaced by one line,
    "...truncated N lines...", where N is the number of lines removed. Otherwise text comes back
    as it is. The result ends with "\\n" exactly when text does. Nothing is sampled: the same text
    always gives the same result. head and tail must not be negative (ValueError).

    Returns (the kept text, N).
    """
    raise NotImplementedError
