"""A live NDJSON feed of the spans an agent run emits, one line per span as it ends."""
from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable
from typing import Any

from .tracer import Span, Tracer


def span_record(span: Span) -> dict[str, Any]:
    """The JSON object for one ended span.

    Ids are lowercase hex, zero-padded: trace_id 32 digits, span_id and parent_span_id
    16 digits; a root's parent_span_id is null. start_ns and end_ns are the integer
    epoch nanoseconds as recorded.
    """
    raise NotImplementedError


async def stream_spans(tracer: Tracer, run: Awaitable[Any]) -> AsyncIterator[str]:
    """Run `run` as a task and yield one NDJSON line (span_record + "\\n") per span of tracer.

    Each line is yielded as soon as its span ends, in the order spans end, while the run is
    still going. Once the run finishes, the lines still waiting are yielded and the generator
    stops; if the run raised, its exception is raised after the last line. Closing the
    generator early cancels the run and waits for it to finish. The feed is attached to the
    tracer only while the generator runs.
    """
    raise NotImplementedError
