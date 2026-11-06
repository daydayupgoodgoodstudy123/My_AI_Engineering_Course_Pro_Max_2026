"""The merge gate: compare a commit's snapshot with main's last-known-good, case by case."""
from __future__ import annotations

from dataclasses import dataclass

from .harness import CATEGORIES
from .store import Snapshot


@dataclass(frozen=True)
class GateReport:
    allowed: bool
    reasons: tuple[str, ...]
    regressed: tuple[str, ...] = ()
    flaky: tuple[str, ...] = ()
    new: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()


def gate(current: Snapshot, baseline: Snapshot | None, limits: dict[str, int]) -> GateReport:
    """Decide whether a commit may merge: no regression above each layer's limit vs main.

    limits gives every category the largest share of its comparable cases that may regress, in
    whole percent. Cases are matched by id. A case is comparable when both snapshots have it and
    it is flaky in neither; it regressed when it passed on main and fails now. A category blocks
    when more than its limit of its comparable cases regressed, so a category with no comparable
    cases never blocks.

    regressed, flaky (flaky here or on main) and new (not on main) list this commit's case ids
    in this commit's order; removed lists the ids main has and this commit lacks, in main's
    order. Flaky, new and removed cases are reported, never counted. reasons has one line per
    blocking category, in CATEGORIES order:
        "<category>: <regressed> of <comparable> comparable cases regressed (limit <limit>%)"
    A commit with no cases blocks with the single reason "no cases". Without a baseline every
    case is new and the commit blocks with the single reason "no baseline on main". A category
    missing from limits raises ValueError.
    """
    raise NotImplementedError
