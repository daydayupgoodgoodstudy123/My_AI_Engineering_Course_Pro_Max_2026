"""In-memory spans for one process (the lesson's SPANS list). Nothing is exported."""
from __future__ import annotations

import itertools
import time
from dataclasses import dataclass, field


@dataclass
class Span:
    name: str
    kind: str
    trace_id: str
    span_id: str
    parent_id: str | None
    attrs: dict = field(default_factory=dict)
    start_ns: int = 0
    end_ns: int = 0


class Tracer:
    def __init__(self) -> None:
        self.spans: list[Span] = []
        self._ids = itertools.count(1)

    def start(
        self, name: str, parent: Span | None, *, kind: str = "INTERNAL", attrs: dict | None = None
    ) -> Span:
        """Open a span. A child joins its parent's trace; a span without a parent starts a new trace."""
        n = next(self._ids)
        span = Span(
            name=name,
            kind=kind,
            trace_id=parent.trace_id if parent else f"{n:032x}",
            span_id=f"{n:016x}",
            parent_id=parent.span_id if parent else None,
            attrs=dict(attrs or {}),
            start_ns=time.time_ns(),
        )
        self.spans.append(span)
        return span

    def finish(self, span: Span) -> None:
        span.end_ns = max(time.time_ns(), span.start_ns + 1)
