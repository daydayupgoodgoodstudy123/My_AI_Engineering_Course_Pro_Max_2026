"""Batch ingestion of span events, pushing session summaries as Server-Sent Events."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import asdict, replace

from .spans import Span
from .summary import SessionSummary, summarize_session


def sse(event_id: int, event: str, data: dict) -> str:
    """One Server-Sent Event: id, event and data lines, then a blank line."""
    return f"id: {event_id}\nevent: {event}\ndata: {json.dumps(data)}\n\n"


class _Stored:
    """A span plus, for each field, the (ts, arrival) stamp of the value it holds."""

    def __init__(self, span: Span, stamp: tuple[int, int]) -> None:
        self.span = span
        self.stamps: dict[str, tuple[int, int]] = {"status": stamp}
        for key in span.attributes:
            self.stamps["attributes." + key] = stamp

    def apply(self, update: dict, stamp: tuple[int, int]) -> None:
        status = self.span.status
        attributes = dict(self.span.attributes)
        if "status" in update and stamp > self.stamps.get("status", (-1, -1)):
            status = update["status"]
            self.stamps["status"] = stamp
        for key, value in update.get("attributes", {}).items():
            field = "attributes." + key
            if stamp > self.stamps.get(field, (-1, -1)):
                attributes[key] = value
                self.stamps[field] = stamp
        self.span = replace(self.span, status=status, attributes=attributes)


async def ingest_stream(
    batches: AsyncIterator[list[dict]], *, orphan_ttl: int = 2
) -> AsyncIterator[str]:
    """Apply batches of span events and yield dashboard updates as SSE, one event per string.

    A "create" event {"kind": "create", "ts": int, "span": {Span fields}} adds a span;
    its status and attributes count as written at the create's ts. A span that
    already exists (same trace_id and span_id) is left as it is.
    An "update" event {"kind": "update", "ts": int, "trace_id", "span_id", and
    "status" and/or "attributes"} changes a span. Each field (the status, and each
    attribute key on its own) keeps the value with the latest ts, whatever order the
    events arrive in; on equal ts the event that arrived later wins.

    An update can arrive before the create of its span. It waits and is applied when
    the create arrives. An update that arrived in batch k and is still waiting at the
    end of batch k + orphan_ttl is dropped; so is any update still waiting when the
    batches run out.

    After each batch, before reading the next one: one "session" event for each session
    whose SessionSummary differs from the last one sent for it, in session_id order,
    with the summary as data (dataclasses.asdict); then, if updates were dropped,
    one "dropped" event with data {"updates": count}. When the batches run out, one more
    "dropped" event reports the updates still waiting, if any. Event ids count 1, 2, 3, ...
    across the whole stream.
    """
    if orphan_ttl < 0:
        raise ValueError("orphan_ttl must be >= 0")
    stored: dict[tuple[str, str], _Stored] = {}
    sessions: dict[str, list[tuple[str, str]]] = {}
    waiting: list[tuple[int, tuple[int, int], dict]] = []  # (batch, stamp, update)
    sent: dict[str, SessionSummary] = {}
    arrival = 0
    batch_no = 0
    next_id = 1

    async for batch in batches:
        batch_no += 1
        touched: set[str] = set()
        for event in batch:
            arrival += 1
            stamp = (event["ts"], arrival)
            if event["kind"] == "create":
                span = Span(**event["span"])
                key = (span.trace_id, span.span_id)
                if key in stored:
                    continue
                entry = stored[key] = _Stored(span, stamp)
                sessions.setdefault(span.session_id, []).append(key)
                for _, early, update in [w for w in waiting if _key(w[2]) == key]:
                    entry.apply(update, early)
                waiting = [w for w in waiting if _key(w[2]) != key]
                touched.add(span.session_id)
            elif event["kind"] == "update":
                entry = stored.get(_key(event))
                if entry is None:
                    waiting.append((batch_no, stamp, event))
                    continue
                entry.apply(event, stamp)
                touched.add(entry.span.session_id)
            else:
                raise ValueError(f"unknown event kind {event['kind']!r}")

        for session_id in sorted(touched):
            summary = summarize_session(session_id, [stored[k].span for k in sessions[session_id]])
            if sent.get(session_id) != summary:
                sent[session_id] = summary
                yield sse(next_id, "session", asdict(summary))
                next_id += 1
        expired = [w for w in waiting if batch_no - w[0] >= orphan_ttl]
        if expired:
            waiting = [w for w in waiting if batch_no - w[0] < orphan_ttl]
            yield sse(next_id, "dropped", {"updates": len(expired)})
            next_id += 1

    if waiting:
        yield sse(next_id, "dropped", {"updates": len(waiting)})


def _key(update: dict) -> tuple[str, str]:
    return (update["trace_id"], update["span_id"])
