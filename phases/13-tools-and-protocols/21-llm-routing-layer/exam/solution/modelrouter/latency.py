"""Latency-aware routing: each request goes to the model that has been fastest lately."""
from __future__ import annotations

import csv
import io
from collections import deque
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Request:
    """A request that needs a model, at t_ms on the gateway's clock."""

    t_ms: int
    request_id: str


@dataclass(frozen=True)
class Result:
    """A finished call: its request, the model that ran it, its status (200 or a 5xx), its latency."""

    t_ms: int
    request_id: str
    model: str
    status: int
    latency_ms: int


FIELDS = ("t_ms", "request_id", "model", "reason")


async def route_by_latency(
    events: AsyncIterator[Request | Result],
    models: Sequence[str],
    *,
    window_ms: int = 60_000,
    trip_after: int = 3,
    cooldown_ms: int = 30_000,
) -> AsyncIterator[str]:
    """Route each request to the model that has been fastest lately, deciding as events arrive.

    Events come in time order. Yield a CSV header record (t_ms,request_id,model,reason) first,
    then one record per Request, as soon as that request arrives.

    Only successful results (status below 500) are latency samples. A sample counts while it
    is less than window_ms old at the request's time; one exactly window_ms old has expired.

    Circuits: trip_after 5xx results in a row from a model open its circuit at the time of the
    last one, and the model gets no requests. Once cooldown_ms have passed, the next request
    goes to it as its one probe, and no other request does until the probe's result arrives:
    a successful probe closes the circuit, a failed one opens it again from that result's time.
    While a circuit is open, other results for the model do not change it.

    Each request goes to, in this order of preference (earliest listed first within a kind):
      probe       a model whose cooldown is over and that has no probe out
      unmeasured  a closed model with no sample in the window
      fastest     the closed model with the lowest median sample (for an even count, the
                  mean of the two middle samples)
    If no model can take the request, its record has an empty model and reason unavailable.
    """
    health = {model: _Health() for model in models}
    yield _record(*FIELDS)
    async for event in events:
        if isinstance(event, Result):
            _observe(health[event.model], event, trip_after)
            continue
        now = event.t_ms
        for model_health in health.values():
            samples = model_health.samples
            while samples and now - samples[0][0] >= window_ms:
                samples.popleft()
        model, reason = _choose(health, models, now, cooldown_ms)
        if reason == "probe":
            health[model].probe = event.request_id
        yield _record(now, event.request_id, model or "", reason)


class _Health:
    def __init__(self) -> None:
        self.samples: deque[tuple[int, int]] = deque()  # (t_ms, latency_ms), oldest first
        self.failures = 0  # 5xx in a row while the circuit is closed
        self.opened_at: int | None = None  # None while the circuit is closed
        self.probe: str | None = None  # request id of the probe that is out


def _observe(health: _Health, result: Result, trip_after: int) -> None:
    ok = result.status < 500
    if ok:
        health.samples.append((result.t_ms, result.latency_ms))
    if health.opened_at is None:
        health.failures = 0 if ok else health.failures + 1
        if health.failures >= trip_after:
            health.opened_at = result.t_ms
            health.failures = 0
    elif result.request_id == health.probe:
        health.probe = None
        health.opened_at = None if ok else result.t_ms


def _choose(health: dict[str, _Health], models: Sequence[str], now: int, cooldown_ms: int) -> tuple[str | None, str]:
    for model in models:
        h = health[model]
        if h.opened_at is not None and h.probe is None and now >= h.opened_at + cooldown_ms:
            return model, "probe"
    closed = [model for model in models if health[model].opened_at is None]
    for model in closed:
        if not health[model].samples:
            return model, "unmeasured"
    if closed:
        return min(closed, key=lambda model: _twice_median(health[model].samples)), "fastest"
    return None, "unavailable"


def _twice_median(samples: deque[tuple[int, int]]) -> int:
    values = sorted(latency for _, latency in samples)
    middle = len(values) // 2
    return 2 * values[middle] if len(values) % 2 else values[middle - 1] + values[middle]


def _record(*fields: object) -> str:
    out = io.StringIO()
    csv.writer(out).writerow(fields)
    return out.getvalue()
