"""A live NDJSON feed of the spans an agent run emits, one line per span as it ends."""
from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator, Awaitable
from typing import Any

from .tracer import Span, Tracer

_DONE = object()


class _QueueProcessor:
    def __init__(self, queue: asyncio.Queue) -> None:
        self.queue = queue

    def on_end(self, span: Span) -> None:
        self.queue.put_nowait(span)


def span_record(span: Span) -> dict[str, Any]:
    """The JSON object for one ended span.

    Ids are lowercase hex, zero-padded: trace_id 32 digits, span_id and parent_span_id
    16 digits; a root's parent_span_id is null. start_ns and end_ns are the integer
    epoch nanoseconds as recorded.
    """
    return {
        "trace_id": f"{span.trace_id:032x}",
        "span_id": f"{span.span_id:016x}",
        "parent_span_id": None if span.parent_span_id is None else f"{span.parent_span_id:016x}",
        "name": span.name,
        "kind": span.kind,
        "start_ns": span.start_ns,
        "end_ns": span.end_ns,
        "attributes": dict(span.attributes),
    }


async def stream_spans(tracer: Tracer, run: Awaitable[Any]) -> AsyncIterator[str]:
    """Run `run` as a task and yield one NDJSON line (span_record + "\\n") per span of tracer.

    Each line is yielded as soon as its span ends, in the order spans end, while the run is
    still going. Once the run finishes, the lines still waiting are yielded and the generator
    stops; if the run raised, its exception is raised after the last line. Closing the
    generator early cancels the run and waits for it to finish. The feed is attached to the
    tracer only while the generator runs.
    """
    queue: asyncio.Queue = asyncio.Queue()
    processor = _QueueProcessor(queue)
    tracer.processors.append(processor)
    task = asyncio.ensure_future(run)
    task.add_done_callback(lambda _: queue.put_nowait(_DONE))
    try:
        while True:
            item = await queue.get()
            if item is _DONE:
                break
            yield json.dumps(span_record(item)) + "\n"
        task.result()
    finally:
        if not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        tracer.processors.remove(processor)
