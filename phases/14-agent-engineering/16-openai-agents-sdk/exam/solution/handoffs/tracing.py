"""Spans for every step of a run, handed to trace processors as they end."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class Span:
    """One step of a run. span_id counts from 1 within its trace, in the order spans start;
    the run span is the root and has no parent_id."""

    trace_id: str
    span_id: int
    parent_id: int | None
    kind: str
    name: str
    attributes: dict[str, Any] = field(default_factory=dict)


class TraceProcessor(Protocol):
    def on_span_end(self, span: Span) -> None: ...


def preview(text: str, limit: int = 40) -> str:
    """Text for a span attribute: whitespace runs become one space, and the result is at most limit
    characters long."""
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


class Trace:
    """The spans of one run: spans in the order they started, ended in the order they ended."""

    def __init__(self, trace_id: str, processors: list[TraceProcessor]) -> None:
        self.trace_id = trace_id
        self.spans: list[Span] = []
        self.ended: list[Span] = []
        self._processors = processors

    def start(self, kind: str, name: str, parent: Span | None = None, **attributes: Any) -> Span:
        span = Span(self.trace_id, len(self.spans) + 1, parent.span_id if parent else None, kind, name, dict(attributes))
        self.spans.append(span)
        return span

    def end(self, span: Span) -> None:
        self.ended.append(span)
        for processor in list(self._processors):
            processor.on_span_end(span)

    @contextmanager
    def span(self, kind: str, name: str, parent: Span | None = None, **attributes: Any) -> Iterator[Span]:
        """A span around a block. When the block raises, the span records the error's class name
        and still ends."""
        span = self.start(kind, name, parent, **attributes)
        try:
            yield span
        except BaseException as exc:
            span.attributes["error"] = type(exc).__name__
            raise
        finally:
            self.end(span)


class Tracing:
    """Starts one trace per run and fans every span out to the trace processors as it ends."""

    def __init__(self) -> None:
        self._processors: list[TraceProcessor] = []
        self._traces = 0

    def add_trace_processor(self, processor: TraceProcessor) -> None:
        """Send every span that ends from now on to processor.on_span_end(span), after the
        processors added before it."""
        self._processors.append(processor)

    def new_trace(self) -> Trace:
        self._traces += 1
        return Trace(f"trace_{self._traces}", self._processors)
