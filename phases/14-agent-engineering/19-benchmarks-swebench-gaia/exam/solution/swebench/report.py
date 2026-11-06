"""Report a benchmark run as more than one number: Verified and SWE-bench+ views, and cost percentiles."""
from __future__ import annotations

from .store import TaskRecord

LEAK_PERCENT = 30
PERCENTILES = (50, 75, 95)
COSTS = ("tokens", "steps", "wall_ms")


def _normalize(line: str) -> str:
    return " ".join(line.split())


def added_lines(diff: str) -> list[str]:
    """The lines a unified diff adds, whitespace-normalized; file headers and blank lines are left out.

    An added line starts with "+" but not with "+++". Its text is the rest of the line with every
    run of whitespace collapsed to one space and the ends stripped.
    """
    out = []
    for line in diff.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            text = _normalize(line[1:])
            if text:
                out.append(text)
    return out


def leaks(issue: str, diff: str) -> bool:
    """SWE-bench+-style solution leakage: was the fix already written out in the issue?

    An added line leaks when, normalized like added_lines, it equals a normalized line of the
    issue. The patch leaks when at least 30% of its added lines leak. A patch that adds no lines
    does not leak.
    """
    added = added_lines(diff)
    if not added:
        return False
    issue_lines = {_normalize(line) for line in issue.splitlines()}
    hits = sum(1 for line in added if line in issue_lines)
    return 100 * hits >= LEAK_PERCENT * len(added)


def nearest_rank(values: list[int], p: int) -> int | None:
    """The p-th percentile by the nearest-rank method: the ceil(p * n / 100)-th smallest value
    (1-based, at least the 1st). None for no values."""
    if not values:
        return None
    rank = max(1, -(-p * len(values) // 100))
    return sorted(values)[rank - 1]


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
    scored = [r for r in records if r.status != "invalid"]
    views = {
        "all": (scored, lambda r: r.status == "resolved"),
        "verified": ([r for r in scored if r.instance_id in verified], lambda r: r.status == "resolved"),
        "plus": (
            scored,
            lambda r: r.status == "resolved" and not leaks(issues[r.instance_id], r.patch),
        ),
    }
    out = {}
    for name, (subset, is_resolved) in views.items():
        resolved = sum(1 for r in subset if is_resolved(r))
        view: dict = {
            "tasks": len(subset),
            "resolved": resolved,
            "rate": resolved / len(subset) if subset else None,
        }
        for cost in COSTS:
            values = sorted(getattr(r, cost) for r in subset)
            view[cost] = {f"p{p}": nearest_rank(values, p) for p in PERCENTILES} if values else None
        out[name] = view
    return out
