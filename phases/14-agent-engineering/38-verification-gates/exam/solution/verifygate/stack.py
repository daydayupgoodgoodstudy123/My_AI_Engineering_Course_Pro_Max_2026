"""Gate a stack of commits, each against the commit it is stacked on."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace

from .checks import COVERAGE_FLOOR_DEFAULT
from .gate import verify
from .model import Artifacts, Verdict


@dataclass(frozen=True)
class StackCommit:
    """One commit of a stack: its sha, the commit it is stacked on, and the gate's artifacts for it.

    artifacts is None while CI has not produced them for this commit.
    """

    sha: str
    parent: str
    artifacts: Artifacts | None = None


@dataclass(frozen=True)
class StackStatus:
    sha: str
    status: str  # passed | failed | waiting
    verdict: Verdict | None  # None while waiting
    blocked_by: str | None


def verify_stack(
    base: str,
    base_coverage: float,
    commits: Iterable[StackCommit],
    overrides: Iterable[dict] = (),
    *,
    secret: bytes,
    strict: bool = False,
    coverage_floor: float = COVERAGE_FLOOR_DEFAULT,
) -> list[StackStatus]:
    """Gate every commit of a stack against the commit it is stacked on, not against main.

    The commits form a tree on base, main's head, whose coverage is base_coverage: each commit's
    parent is base or another commit of the stack. A parent that is neither, a commit that cannot be
    reached from base, or a sha given twice raises ValueError.

    A commit is verified with verify() on its own artifacts and the overrides, so an override signed
    for one commit's HEAD does not reach another. Its coverage "previous" is the coverage it is stacked
    on: its parent's current coverage, or, when the parent has no coverage report, whatever the parent
    was compared against, down to base_coverage. The artifacts passed in are not changed.

    A commit is waiting, with no verdict, when it has no artifacts, when its artifacts were made at
    another commit (artifacts.head_commit is not its sha), or when its parent is waiting: without the
    parent's report there is nothing to compare against. blocked_by is the first commit from the
    bottom of the stack up to this one, itself included, that has not passed; None means this commit
    can land.

    The result has one status per commit, parents before children, depth first, children in the
    order they were given.
    """
    commits = list(commits)
    overrides = list(overrides)
    by_sha: dict[str, StackCommit] = {}
    for commit in commits:
        if commit.sha == base or commit.sha in by_sha:
            raise ValueError(f"commit {commit.sha} is given twice")
        by_sha[commit.sha] = commit
    children: dict[str, list[StackCommit]] = {}
    for commit in commits:
        if commit.parent != base and commit.parent not in by_sha:
            raise ValueError(f"{commit.sha} is stacked on {commit.parent}, which is neither {base} nor in the stack")
        children.setdefault(commit.parent, []).append(commit)

    out: list[StackStatus] = []
    todo = [(commit, base_coverage, False, None) for commit in reversed(children.get(base, []))]
    while todo:
        commit, baseline, parent_waiting, blocker = todo.pop()
        art = commit.artifacts
        if parent_waiting or art is None or art.head_commit != commit.sha:
            status, verdict, onward = "waiting", None, baseline
        else:
            coverage = art.coverage_report
            if coverage:
                coverage = {**coverage, "previous": baseline}
            verdict = verify(
                replace(art, coverage_report=coverage),
                overrides,
                secret=secret,
                strict=strict,
                coverage_floor=coverage_floor,
            )
            status = "passed" if verdict.passed else "failed"
            onward = float(coverage["current"]) if coverage and "current" in coverage else baseline
        blocker = blocker or (None if status == "passed" else commit.sha)
        out.append(StackStatus(commit.sha, status, verdict, blocker))
        for child in reversed(children.get(commit.sha, [])):
            todo.append((child, onward, status == "waiting", blocker))

    if len(out) != len(commits):
        stranded = sorted(set(by_sha) - {status.sha for status in out})
        raise ValueError(f"not connected to {base}: {', '.join(stranded)}")
    return out
