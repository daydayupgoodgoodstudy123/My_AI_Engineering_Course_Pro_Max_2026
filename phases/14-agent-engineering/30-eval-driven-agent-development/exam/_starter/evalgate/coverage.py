"""Coverage map: every guardrail and every learned rule must be backed by a passing eval case."""
from __future__ import annotations

from dataclasses import dataclass

from .store import Snapshot

KINDS = ("guardrail", "rule")


@dataclass(frozen=True)
class Requirement:
    """A guardrail or a learned rule. A rule learned on top of earlier ones names them in
    derived_from."""

    name: str
    kind: str
    derived_from: tuple[str, ...] = ()


@dataclass(frozen=True)
class CoverageReport:
    covered: dict[str, tuple[str, ...]]
    uncovered: dict[str, tuple[str, ...]]


def coverage(
    requirements: list[Requirement],
    covers: dict[str, tuple[str, ...]],
    snapshot: Snapshot,
) -> CoverageReport:
    """Check which guardrails and learned rules are backed by a passing eval case.

    covers maps a case id to the requirement names the case exercises. A case backs those
    requirements when it is in the snapshot, passed, and is not flaky. A requirement is covered
    when at least one case backs it and every requirement it derives from is covered, all the
    way up.

    covered maps each covered requirement to the ids of the cases that back it, in snapshot
    order. uncovered maps every other requirement to the chain that explains why: (name,) when
    no case backs it, otherwise name followed by the chain of its first uncovered parent in
    derived_from order. Both dicts list requirements in the order given.

    An unknown kind, a name given twice, a covers or derived_from entry that names no
    requirement, and a requirement that derives from itself, directly or through others, raise
    ValueError.
    """
    raise NotImplementedError
