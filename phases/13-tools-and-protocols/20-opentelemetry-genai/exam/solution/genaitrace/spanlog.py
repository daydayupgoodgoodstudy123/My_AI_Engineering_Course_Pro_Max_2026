"""An append-only log of finished spans: one OTLP/JSON span object per line."""
from __future__ import annotations

import json
from pathlib import Path

from .otlp import from_otlp, to_otlp
from .tracer import Span


class SpanLog:
    """Finished spans in a JSONL file, one to_otlp object per line, in the order they were appended.

    Opening an existing log keeps what is in it, and append adds to the end. spans() reads the file
    and returns spans equal to the ones appended, field for field: nanosecond timestamps, ids,
    attribute types (1 stays an int, 1.0 a float, True a bool), arrays, and events in order.
    A span that cannot be logged (it has not ended, or an attribute cannot be encoded) raises
    ValueError and leaves the file as it was.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._file = open(self.path, "a", encoding="utf-8")

    def append(self, span: Span) -> None:
        line = json.dumps(to_otlp(span), separators=(",", ":")) + "\n"
        self._file.write(line)
        self._file.flush()

    def spans(self) -> list[Span]:
        with open(self.path, encoding="utf-8") as f:
            return [from_otlp(json.loads(line)) for line in f]

    def close(self) -> None:
        self._file.close()
