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
    by_name: dict[str, Requirement] = {}
    for req in requirements:
        if req.kind not in KINDS:
            raise ValueError(f"{req.name!r} has unknown kind {req.kind!r}")
        if req.name in by_name:
            raise ValueError(f"requirement {req.name!r} is given twice")
        by_name[req.name] = req
    for req in requirements:
        unknown = [parent for parent in req.derived_from if parent not in by_name]
        if unknown:
            raise ValueError(f"{req.name!r} derives from unknown {unknown}")
    for cid, names in covers.items():
        unknown = [name for name in names if name not in by_name]
        if unknown:
            raise ValueError(f"case {cid!r} covers unknown {unknown}")

    backers: dict[str, list[str]] = {name: [] for name in by_name}
    for case in snapshot.cases:
        if case.passed and not case.flaky:
            for name in covers.get(case.cid, ()):
                if case.cid not in backers[name]:
                    backers[name].append(case.cid)

    gaps: dict[str, tuple[str, ...]] = {}
    active: set[str] = set()

    def gap(name: str) -> tuple[str, ...]:
        if name in gaps:
            return gaps[name]
        if name in active:
            raise ValueError(f"{name!r} derives from itself")
        active.add(name)
        parents = [gap(parent) for parent in by_name[name].derived_from]
        active.discard(name)
        if not backers[name]:
            found: tuple[str, ...] = (name,)
        else:
            found = next(((name,) + chain for chain in parents if chain), ())
        gaps[name] = found
        return found

    for req in requirements:
        gap(req.name)
    return CoverageReport(
        {r.name: tuple(backers[r.name]) for r in requirements if not gaps[r.name]},
        {r.name: gaps[r.name] for r in requirements if gaps[r.name]},
    )
