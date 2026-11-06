"""Which surface stops each failure first, and which missing surface to add next."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

# A failure meets the surfaces in the order of the lesson's flowchart: the scope contract,
# repo memory (state), the agent loop, whose startup reads the instructions, runtime
# feedback, the verification gate, the reviewer and the handoff.
FLOW_ORDER = ["scope", "state", "instructions", "feedback", "verification", "review", "handoff"]


@dataclass(frozen=True)
class Failure:
    failure_id: str
    catchers: tuple[str, ...]  # the surfaces built to stop this failure, in any order


@dataclass
class CatchReport:
    caught: dict[str, str]  # failure id -> the surface that stops it first
    escaped: list[str]  # ids of the failures no present surface stops, in input order
    counts: dict[str, int]  # every surface, in FLOW_ORDER -> failures it stops first
    next_surfaces: list[str]  # missing surfaces to add, most leverage first


def catch_matrix(failures: list[Failure], present: Iterable[str], limit: int = 3) -> CatchReport:
    """Send every failure along the flow and record which surface stops it.

    A failure is stopped by the first present surface, in FLOW_ORDER, among its catchers.
    A failure with no present catcher escapes; one that no surface is built for escapes
    even the full workbench.

    next_surfaces answers the workbench-audit skill's question: which missing surface, if
    added first, removes the most failure modes. Pick the missing surface that would stop
    the most of the failures that still escape, add it, and pick again, at most limit
    times. A tie goes to the surface earlier in FLOW_ORDER. A surface that would stop
    nothing is never picked.

    Unknown surface names and duplicate failure ids raise ValueError.
    """
    present = set(present)
    ids = [failure.failure_id for failure in failures]
    if len(set(ids)) != len(ids):
        raise ValueError("failure ids must be unique")
    named = present.union(*(failure.catchers for failure in failures))
    unknown = named - set(FLOW_ORDER)
    if unknown:
        raise ValueError(f"unknown surfaces: {sorted(unknown)}")

    caught: dict[str, str] = {}
    escaped: list[Failure] = []
    counts = dict.fromkeys(FLOW_ORDER, 0)
    for failure in failures:
        stop = next((s for s in FLOW_ORDER if s in present and s in failure.catchers), None)
        if stop is None:
            escaped.append(failure)
        else:
            caught[failure.failure_id] = stop
            counts[stop] += 1

    picks: list[str] = []
    remaining = escaped
    while len(picks) < limit:
        gains = {
            s: sum(s in failure.catchers for failure in remaining)
            for s in FLOW_ORDER
            if s not in present and s not in picks
        }
        best = max(gains, key=gains.__getitem__, default=None)  # the first maximum in FLOW_ORDER
        if best is None or gains[best] == 0:
            break
        picks.append(best)
        remaining = [failure for failure in remaining if best not in failure.catchers]
    return CatchReport(caught, [failure.failure_id for failure in escaped], counts, picks)
