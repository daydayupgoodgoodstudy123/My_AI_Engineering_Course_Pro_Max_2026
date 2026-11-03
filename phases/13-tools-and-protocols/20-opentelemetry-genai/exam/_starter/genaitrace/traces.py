"""Group finished spans into traces and link every span to its parent."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from .tracer import Span


@dataclass
class Trace:
    trace_id: str
    spans: list[Span] = field(default_factory=list)  # every span of the trace, in the order given
    roots: list[Span] = field(default_factory=list)  # spans with no parent in the trace, in the order given
    children: dict[str, list[Span]] = field(default_factory=dict)  # span id -> children, in the order given

    def children_of(self, span: Span) -> list[Span]:
        return self.children.get(span.span_id, [])


def link(spans: Iterable[Span]) -> list[Trace]:
    """Group spans by trace id and link every span to its parent.

    Traces come in the order their first span appears. A span whose parent_span_id names another span
    of the same trace is that span's child; span ids only need to be unique within a trace. A span
    with no parent, or whose parent is not among the spans given (it ran in another process, or went
    out in another batch), is a root of its trace and keeps its parent_span_id, so a backend can
    still join it to the caller's span.
    """
    spans = list(spans)
    traces: dict[str, Trace] = {}
    for span in spans:
        trace = traces.get(span.trace_id)
        if trace is None:
            trace = traces[span.trace_id] = Trace(span.trace_id)
        trace.spans.append(span)
        parent = _find(spans, span.trace_id, span.parent_span_id)
        if parent is None:
            trace.roots.append(span)
        else:
            trace.children.setdefault(parent.span_id, []).append(span)
    return list(traces.values())


def _find(spans: list[Span], trace_id: str, span_id: str | None) -> Span | None:
    """The span with this id in this trace, if it is among spans."""
    if span_id is None:
        return None
    return next((span for span in spans if span.span_id == span_id and span.trace_id == trace_id), None)
