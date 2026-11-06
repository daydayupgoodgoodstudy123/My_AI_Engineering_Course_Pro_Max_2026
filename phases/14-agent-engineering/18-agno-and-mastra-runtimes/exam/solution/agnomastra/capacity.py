"""Capacity planning for an agent request path with Little's law: where does the time go?"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction

NS_PER = {"ns": 1, "us": 10**3, "\u03bcs": 10**3, "\u00b5s": 10**3, "ms": 10**6, "s": 10**9}
_DURATION = re.compile(r"(\d+(?:\.\d+)?)(ns|us|\u03bcs|\u00b5s|ms|s)")


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
    match = _DURATION.fullmatch(text)
    if match is None:
        raise ValueError(f"unknown duration {text!r}")
    value = Decimal(match[1]) * NS_PER[match[2]]
    if value != value.to_integral_value():
        raise ValueError(f"{text!r} is not a whole number of nanoseconds")
    return int(value)


def plan(rate: int | Fraction, stages: list[Stage]) -> Plan:
    """Apply Little's law to every stage of a request path at `rate` requests per second.

    in_flight = rate x service time, and utilization = in_flight / workers. A stage at
    utilization 1 or more cannot keep up, so the plan is sustainable only when every stage stays
    below 1. The bottleneck is the stage with the highest utilization; a tie goes to the stage
    with the longer service time, then to the earlier stage. Every number is exact.
    Raises ValueError for no stages, repeated names, a negative rate, workers below 1, or a
    zero service time.
    """
    if not stages:
        raise ValueError("a plan needs at least one stage")
    if len({s.name for s in stages}) != len(stages):
        raise ValueError("stage names must be unique")
    rate = Fraction(rate)
    if rate < 0:
        raise ValueError("rate must not be negative")
    loads = []
    for stage in stages:
        if stage.workers < 1:
            raise ValueError(f"{stage.name}: workers must be at least 1")
        service_ns = parse_duration(stage.service_time)
        if service_ns == 0:
            raise ValueError(f"{stage.name}: service time must be positive")
        in_flight = rate * Fraction(service_ns, 10**9)
        loads.append(
            StageLoad(
                stage.name,
                service_ns,
                in_flight,
                in_flight / stage.workers,
                math.floor(in_flight) + 1,
            )
        )
    order = sorted(range(len(loads)), key=lambda i: (-loads[i].utilization, -loads[i].service_ns, i))
    return Plan(
        loads=loads,
        bottleneck=loads[order[0]].name,
        sustainable=all(load.utilization < 1 for load in loads),
        max_rate=min(Fraction(s.workers * 10**9, l.service_ns) for s, l in zip(stages, loads)),
        latency_ns=sum(load.service_ns for load in loads),
    )


def latency_saving(stages: list[Stage], name: str, service_time: str) -> Fraction:
    """The share of the end-to-end service time saved if stage `name` took service_time instead.

    Negative when the new time is slower. An unknown stage name raises KeyError.
    """
    times = {s.name: parse_duration(s.service_time) for s in stages}
    if name not in times:
        raise KeyError(name)
    total = sum(times.values())
    return Fraction(times[name] - parse_duration(service_time), total)
