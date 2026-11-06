"""GenAI-shaped spans and the collector that stores them."""
from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Span:
    """One span as the collector stores it.

    span_id is unique within its trace, not across traces. parent_id is the
    span_id of the parent span in the same trace, or None for a root.
    """

    trace_id: str
    span_id: str
    session_id: str
    name: str
    parent_id: str | None = None
    start_ns: int = 0
    status: str = "ok"
    attributes: dict[str, Any] = field(default_factory=dict)


def load_spans(lines: Iterable[str]) -> list[Span]:
    """Parse exported spans, one JSON object per line. Blank lines are skipped.

    Some exporters write numbers as strings ("tokens": "800"). After loading,
    the "tokens" attribute is always an int.
    """
    spans = []
    for line in lines:
        if not line.strip():
            continue
        obj = json.loads(line)
        attributes = dict(obj.get("attributes", {}))
        if "tokens" in attributes:
            attributes["tokens"] = int(attributes["tokens"])
        spans.append(
            Span(
                trace_id=obj["trace_id"],
                span_id=obj["span_id"],
                session_id=obj["session_id"],
                name=obj["name"],
                parent_id=obj.get("parent_id"),
                start_ns=obj.get("start_ns", 0),
                status=obj.get("status", "ok"),
                attributes=attributes,
            )
        )
    return spans


class TraceCollector:
    """Spans in arrival order."""

    def __init__(self) -> None:
        self._spans: list[Span] = []
        self._seen: set[tuple[str, str]] = set()

    def ingest(self, span: Span) -> bool:
        """Store a span and return True.

        Exporters retry, so the same span (same trace_id and span_id) can arrive
        more than once. Only the first copy is kept; a repeat returns False.
        """
        key = (span.trace_id, span.span_id)
        if key in self._seen:
            return False
        self._seen.add(key)
        self._spans.append(span)
        return True

    def spans(self) -> list[Span]:
        """Every stored span, in arrival order."""
        return list(self._spans)

    def sessions(self) -> list[str]:
        """Session ids, in the order their first span arrived."""
        return list(dict.fromkeys(span.session_id for span in self._spans))

    def by_session(self) -> dict[str, list[Span]]:
        """Spans grouped by session; sessions and spans in arrival order."""
        result: dict[str, list[Span]] = {}
        for span in self._spans:
            result.setdefault(span.session_id, []).append(span)
        return result
