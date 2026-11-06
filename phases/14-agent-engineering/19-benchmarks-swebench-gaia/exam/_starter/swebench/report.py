"""Report a benchmark run as more than one number: Verified and SWE-bench+ views, and cost percentiles."""
from __future__ import annotations

from .store import TaskRecord

LEAK_PERCENT = 30
PERCENTILES = (50, 75, 95)
COSTS = ("tokens", "steps", "wall_ms")


def added_lines(diff: str) -> list[str]:
    """The lines a unified diff adds, whitespace-normalized; file headers and blank lines are left out.

    An added line starts with "+" but not with "+++". Its text is the rest of the line with every
    run of whitespace collapsed to one space and the ends stripped.
    """
    raise NotImplementedError


def leaks(issue: str, diff: str) -> bool:
    """SWE-bench+-style solution leakage: was the fix already written out in the issue?

    An added line leaks when, normalized like added_lines, it equals a normalized line of the
    issue. The patch leaks when at least 30% of its added lines leak. A patch that adds no lines
    does not leak.
    """
    raise NotImplementedError


def nearest_rank(values: list[int], p: int) -> int | None:
    """The p-th percentile by the nearest-rank method: the ceil(p * n / 100)-th smallest value
    (1-based, at least the 1st). None for no values."""
    raise NotImplementedError


def report(records: list[TaskRecord], issues: dict[str, str], verified: set[str]) -> dict:
    """Resolution rates and cost distributions for one run, in three views.

    A record is scored unless its status is "invalid"; an "error" record is scored and is not
    resolved. "all" covers every scored record, "verified" the scored records whose instance id
    is in verified (the SWE-bench Verified subset). "plus" covers the same records as "all", but
    a resolved record whose patch leaks the solution from its issue counts as unresolved, as in
    the SWE-bench+ audit.

    Each view is {"tasks": n, "resolved": r, "rate": r / n, "tokens": {"p50", "p75", "p95"},
    "steps": {...}, "wall_ms": {...}}, with nearest-rank percentiles over the view's records.
    A view with no records has rate None and None for each cost.
    """
    raise NotImplementedError
