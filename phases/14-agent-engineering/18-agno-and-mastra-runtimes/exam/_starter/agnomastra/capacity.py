"""Capacity planning for an agent request path with Little's law: where does the time go?"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class Stage:
    name: str
    service_time: str  # "2μs", "40ms", "1.8s"
    workers: int  # how many requests the stage can serve at once


@dataclass(frozen=True)
class StageLoad:
    name: str
    service_ns: int
    in_flight: Fraction  # requests inside the stage on average
    utilization: Fraction  # in_flight / workers
    workers_needed: int  # the fewest workers that keep utilization below 1


@dataclass(frozen=True)
class Plan:
    loads: list[StageLoad]
    bottleneck: str
    sustainable: bool
    max_rate: Fraction  # the arrival rate (requests/s) at which the bottleneck saturates
    latency_ns: int  # end-to-end service time, before any queueing


def parse_duration(text: str) -> int:
    """A duration such as "750ns", "2us", "2μs", "40ms" or "1.8s", in whole nanoseconds.

    Microseconds may be written us, μs (Greek mu, U+03BC) or µs (micro sign, U+00B5).
    Unknown units, signs, spaces, and values that are not a whole number of nanoseconds
    raise ValueError.
    """
    raise NotImplementedError


def plan(rate: int | Fraction, stages: list[Stage]) -> Plan:
    """Apply Little's law to every stage of a request path at `rate` requests per second.

    in_flight = rate x service time, and utilization = in_flight / workers. A stage at
    utilization 1 or more cannot keep up, so the plan is sustainable only when every stage stays
    below 1. The bottleneck is the stage with the highest utilization; a tie goes to the stage
    with the longer service time, then to the earlier stage. Every number is exact.
    Raises ValueError for no stages, repeated names, a negative rate, workers below 1, or a
    zero service time.
    """
    raise NotImplementedError


def latency_saving(stages: list[Stage], name: str, service_time: str) -> Fraction:
    """The share of the end-to-end service time saved if stage `name` took service_time instead.

    Negative when the new time is slower. An unknown stage name raises KeyError.
    """
    raise NotImplementedError
