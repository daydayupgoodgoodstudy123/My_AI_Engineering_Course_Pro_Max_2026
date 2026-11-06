"""A live routing desk: tickets are classified as they arrive and handled by their route."""
from __future__ import annotations

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
    raise NotImplementedError
