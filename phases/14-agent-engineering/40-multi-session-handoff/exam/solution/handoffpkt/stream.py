"""Trim a feedback log of any length in one pass."""
from __future__ import annotations

import json
from collections import deque
from collections.abc import Iterable, Iterator

from .packet import TAIL_K, failed


def trim_stream(records: Iterable[dict], k: int = TAIL_K) -> Iterator[str]:
    """The trimmed feedback log as JSON Lines: the last k records plus every earlier record
    that failed (exit_code is not 0; None is a failure), in log order.

    The log may be far too long to hold: read it once, keep at most the last k records in
    memory, and yield each kept record, one JSON object followed by "\\n", as soon as no
    earlier record can still come before it. A failure among the last k is written once, like
    any other record, and two equal records are two lines.
    """
    window: deque[dict] = deque()
    for record in records:
        window.append(record)
        if len(window) > k:
            oldest = window.popleft()
            if failed(oldest):
                yield json.dumps(oldest, ensure_ascii=False) + "\n"
    while window:
        yield json.dumps(window.popleft(), ensure_ascii=False) + "\n"
