"""Bisect a quality regression to the prompt version that introduced it."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class Bisection:
    last_good: str
    culprit: str | None
    suspects: list[str]


def bisect_versions(
    results: Iterable[tuple[str, str]],
    known_good: str,
    *,
    min_traces: int = 10,
    max_drop: int = 10,
) -> Bisection:
    """Find the first prompt version after known_good whose pass rate regressed.

    results holds one (prompt_version, verdict) pair per judged trace. A version's
    pass rate is the share of its traces judged PASS. A version with fewer than
    min_traces traces is inconclusive: it is neither good nor the culprit.

    Versions are written like v1.9 or v1.10 and are walked in version order,
    starting after known_good. Each conclusive version is compared with known_good's
    own pass rate (not with the version before it, so a slow drift still shows up).
    It regresses when its rate is more than max_drop percentage points below; a drop
    of exactly max_drop does not count.

    culprit is the first version that regresses, or None. last_good is the newest
    conclusive version before the culprit that did not regress (known_good if none
    did). suspects are the versions after last_good up to and including the culprit,
    since an inconclusive version among them may hold the change; it is empty when
    there is no culprit. known_good missing or inconclusive raises ValueError.
    """
    raise NotImplementedError
