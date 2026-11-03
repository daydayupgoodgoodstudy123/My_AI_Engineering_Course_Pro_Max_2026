"""Replay a resource server's timeline and keep a CSV decision log, one row per request."""
from __future__ import annotations

import csv
import io
from collections.abc import AsyncIterator

from .clock import ManualClock
from .gate import Gate
from .idp import Unavailable
from .jwt import TokenError, parse

COLUMNS = ("t_ms", "kid", "decision", "reason", "health")


async def replay(events: AsyncIterator[dict], gate: Gate, clock: ManualClock) -> AsyncIterator[str]:
    """Drive the gate through a timeline and log every decision as it is made.

    Events arrive in time order, each with an integer t_ms. clock reads t_ms / 1000 while the
    event is handled.
      {"type": "refresh", "issuer": ...}  the scheduled JWKS refresh job runs for that issuer.
          A refresh that fails leaves the cache as it was, and the replay goes on.
      {"type": "request", "token": ..., "scope": ...}  a bearer token arrives for a tool that
          needs scope; the gate decides it.
    Anything else raises ValueError.

    The output is CSV. The first chunk is the header t_ms,kid,decision,reason,health; after it,
    one chunk holds exactly one record per request, yielded as soon as the request is decided.
    kid is the token header's kid exactly as sent, or "" when the token is not a JWT or its kid
    is not a string.
    """
    yield _record(COLUMNS)
    async for event in events:
        clock.now = event["t_ms"] / 1000
        kind = event.get("type")
        if kind == "refresh":
            try:
                gate.server.refresh_jwks(event["issuer"])
            except Unavailable:
                pass
        elif kind == "request":
            outcome = gate.check(event["token"], event["scope"])
            yield _record((event["t_ms"], _kid(event["token"]), outcome.decision, outcome.reason, outcome.health))
        else:
            raise ValueError(f"unknown event type {kind!r}")


def _record(fields) -> str:
    buffer = io.StringIO()
    csv.writer(buffer).writerow(fields)
    return buffer.getvalue()


def _kid(token: str) -> str:
    try:
        header, _ = parse(token)
    except TokenError:
        return ""
    kid = header.get("kid")
    return kid if isinstance(kid, str) else ""
