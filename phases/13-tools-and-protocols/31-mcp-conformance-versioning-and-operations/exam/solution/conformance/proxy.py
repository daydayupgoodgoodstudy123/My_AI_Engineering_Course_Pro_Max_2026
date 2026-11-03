"""Proxy evidence: stitch the ingress, origin and egress captures of each exchange, and report
every exchange as TAP."""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from .evidence import redact

VIEWS = ("ingress", "origin", "egress")
COLLAPSED = "proxy collapsed a protocol error into HTTP 500"
STATUS_CHANGED = "proxy changed the HTTP status"
BODY_CHANGED = "proxy changed the origin JSON-RPC body"


def judge_exchange(ingress: dict[str, Any], origin: dict[str, Any], egress: dict[str, Any]) -> list[str]:
    """What the proxy did to one exchange: an empty list when it preserved it.

    Views come from different collectors, and some collectors redact before they ship, so
    the views are compared after redact(). Problems, in this order:
      COLLAPSED       the origin answered 400 or 404 with a JSON-RPC error and the client got 500
      STATUS_CHANGED  the client got any other status than the origin sent
      BODY_CHANGED    the client got another body than the origin sent
    """
    origin, egress = redact(origin), redact(egress)
    problems: list[str] = []
    origin_body = origin.get("body")
    if (
        origin.get("status") in (400, 404)
        and isinstance(origin_body, dict)
        and "error" in origin_body
        and egress.get("status") == 500
    ):
        problems.append(COLLAPSED)
    elif egress.get("status") != origin.get("status"):
        problems.append(STATUS_CHANGED)
    if egress.get("body") != origin_body:
        problems.append(BODY_CHANGED)
    return problems


async def proxy_tap(events: AsyncIterator[dict[str, Any]], timeout_ms: int = 5000) -> AsyncIterator[str]:
    """Stitch proxy captures by exchange and report every exchange as one TAP line.

    An event is one view of one exchange: {"exchange": id, "view": one of VIEWS, "at": capture
    time in milliseconds, ...the view's own fields}. Views arrive in any order, and a collector
    may deliver one twice: the first copy counts, later copies are ignored, and so is anything
    that arrives for an exchange already reported.

    An exchange is reported the moment its third view arrives, judged by judge_exchange:
    "ok N - <id>", or "not ok N - <id> # <problems joined by '; '>".
    An exchange's deadline is timeout_ms after the "at" of its first event. The clock is the
    largest "at" seen so far. After each event, every open exchange whose deadline is behind
    the clock is reported, in the order the exchanges first appeared, as
    "not ok N - <id> # incomplete evidence: missing <views in VIEWS order, joined by ', '>".
    When the events end, every exchange still open is reported that way, then comes the plan
    "1..N". N counts reported exchanges from 1, and every line ends with a newline.
    """
    pending: dict[str, dict[str, dict[str, Any]]] = {}
    deadlines: dict[str, int] = {}
    reported: set[str] = set()
    clock: int | None = None
    count = 0

    def line(exchange: str, problems: list[str]) -> str:
        nonlocal count
        count += 1
        reported.add(exchange)
        if not problems:
            return f"ok {count} - {exchange}\n"
        return f"not ok {count} - {exchange} # {'; '.join(problems)}\n"

    def incomplete(exchange: str) -> str:
        views = pending.pop(exchange)
        missing = ", ".join(view for view in VIEWS if view not in views)
        return line(exchange, [f"incomplete evidence: missing {missing}"])

    async for event in events:
        exchange, view, at = event["exchange"], event["view"], event["at"]
        if view not in VIEWS:
            raise ValueError(f"unknown view {view!r}")
        clock = at if clock is None else max(clock, at)
        if exchange not in reported:
            views = pending.setdefault(exchange, {})
            deadlines.setdefault(exchange, at + timeout_ms)
            views.setdefault(view, event)
            if len(views) == len(VIEWS):
                del pending[exchange]
                yield line(exchange, judge_exchange(views["ingress"], views["origin"], views["egress"]))
        for overdue in [name for name in pending if deadlines[name] < clock]:
            yield incomplete(overdue)
    for left in list(pending):
        yield incomplete(left)
    yield f"1..{count}\n"
