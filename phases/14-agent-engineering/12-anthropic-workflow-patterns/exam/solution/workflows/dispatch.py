"""A live routing desk: tickets are classified as they arrive and handled by their route."""
from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Ticket:
    id: str
    text: str


async def route_stream(
    tickets: AsyncIterator[Ticket],
    classifier: Callable[[str], Awaitable[str]],
    handlers: dict[str, Callable[[str], Awaitable[str]]],
    limits: dict[str, int],
) -> AsyncIterator[str]:
    """Route tickets as they arrive and yield one NDJSON line per ticket, in the order they finish.

    Each ticket is classified as soon as it arrives, and its label is normalized as route() does it
    (surrounding whitespace removed, then lowercased). At most limits[label] tickets of one route are
    in that route's handler at once (limits has an entry for every handler), and a busy route never
    holds up tickets for any other route.

    A handled ticket yields {"ticket": id, "route": label, "output": output, "ms": ms}. A ticket whose
    label has no handler yields {"ticket": id, "route": label, "error": "unknown route", "ms": ms}; one
    whose handler raises yields "error": "<ExceptionType>: <message>" instead, and the stream carries
    on. ms is the time from the ticket's arrival to its line, in milliseconds. Each line is one JSON
    object and a "\\n", yielded as soon as its ticket is done. Closing the stream early stops pulling
    tickets and cancels the ones still in flight, since their lines would have nowhere to go.
    """
    gates = {label: asyncio.Semaphore(limits[label]) for label in handlers}
    lines: asyncio.Queue = asyncio.Queue()
    in_flight: set[asyncio.Task] = set()

    async def handle(ticket: Ticket, arrived: float) -> None:
        label = None
        try:
            label = (await classifier(ticket.text)).strip().lower()
            if label not in handlers:
                record = {"ticket": ticket.id, "route": label, "error": "unknown route"}
            else:
                async with gates[label]:
                    output = await handlers[label](ticket.text)
                record = {"ticket": ticket.id, "route": label, "output": output}
        except Exception as exc:
            record = {"ticket": ticket.id, "route": label, "error": f"{type(exc).__name__}: {exc}"}
        record["ms"] = round((time.perf_counter() - arrived) * 1000, 3)
        lines.put_nowait(json.dumps(record, ensure_ascii=False) + "\n")

    async def intake() -> None:
        try:
            async for ticket in tickets:
                task = asyncio.create_task(handle(ticket, time.perf_counter()))
                in_flight.add(task)
                task.add_done_callback(in_flight.discard)
            if in_flight:
                await asyncio.wait(set(in_flight))
        finally:
            lines.put_nowait(None)

    feeder = asyncio.create_task(intake())
    try:
        while (line := await lines.get()) is not None:
            yield line
        await feeder  # re-raises an error from the ticket source
    finally:
        pending = [feeder, *in_flight]
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
