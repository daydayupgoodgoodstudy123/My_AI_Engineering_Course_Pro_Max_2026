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
    raise NotImplementedError
