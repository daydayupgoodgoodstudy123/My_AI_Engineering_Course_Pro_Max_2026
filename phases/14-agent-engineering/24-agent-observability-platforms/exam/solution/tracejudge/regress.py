"""Bisect a quality regression to the prompt version that introduced it."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class Bisection:
    last_good: str
    culprit: str | None
    suspects: list[str]


def version_key(version: str) -> tuple[int, ...]:
    """Sort key for versions written v<int>.<int>[.<int>...]: v1.9 comes before v1.10."""
    if not version.startswith("v"):
        raise ValueError(f"bad prompt version {version!r}")
    try:
        return tuple(int(part) for part in version[1:].split("."))
    except ValueError:
        raise ValueError(f"bad prompt version {version!r}") from None


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
    counts: dict[str, list[int]] = {}
    for version, verdict in results:
        tally = counts.setdefault(version, [0, 0])
        tally[0] += verdict == "PASS"
        tally[1] += 1
    if known_good not in counts or counts[known_good][1] < min_traces:
        raise ValueError(f"known-good version {known_good!r} has fewer than {min_traces} traces")
    base_pass, base_n = counts[known_good]
    good_key = version_key(known_good)

    last_good = known_good
    since_good: list[str] = []
    for version in sorted(counts, key=version_key):
        if version_key(version) <= good_key:
            continue
        passed, n = counts[version]
        since_good.append(version)
        if n < min_traces:
            continue
        # drop in points = 100 * (base_pass/base_n - passed/n), compared exactly
        if 100 * (base_pass * n - passed * base_n) > max_drop * base_n * n:
            return Bisection(last_good, version, since_good)
        last_good = version
        since_good = []
    return Bisection(last_good, None, [])
