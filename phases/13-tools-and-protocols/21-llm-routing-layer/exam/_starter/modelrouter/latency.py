"""Latency-aware routing: each request goes to the model that has been fastest lately."""
from __future__ import annotations

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
    raise NotImplementedError
