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
    raise NotImplementedError
