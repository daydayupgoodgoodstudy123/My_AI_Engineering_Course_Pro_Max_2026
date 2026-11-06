"""Batch ingestion of span events, pushing session summaries as Server-Sent Events."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import asdict

from .spans import Span
from .summary import SessionSummary, summarize_session


def sse(event_id: int, event: str, data: dict) -> str:
    """One Server-Sent Event: id, event and data lines, then a blank line."""
    return f"id: {event_id}\nevent: {event}\ndata: {json.dumps(data)}\n\n"


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
    raise NotImplementedError
