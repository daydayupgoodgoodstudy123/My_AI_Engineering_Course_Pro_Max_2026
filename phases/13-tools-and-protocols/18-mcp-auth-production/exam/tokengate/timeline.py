"""Replay a resource server's timeline and keep a CSV decision log, one row per request."""
from __future__ import annotations

from collections.abc import AsyncIterator

from .clock import ManualClock
from .gate import Gate

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
    raise NotImplementedError
