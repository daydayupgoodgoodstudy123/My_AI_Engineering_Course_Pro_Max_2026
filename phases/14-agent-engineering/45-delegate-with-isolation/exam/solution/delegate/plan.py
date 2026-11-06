"""Exclusive write claims and a delegation-plan preview."""
from pathlib import PurePosixPath
from dataclasses import dataclass
from .model import WorkUnit
from .support import safe_waves


def claim_parts(path: str) -> tuple[str, ...]:
    """Normalize dot segments, repeated separators and trailing slash lexically.

    Inputs are relative and contain no '..'. '.' means the whole repository.
    This is claim matching, not filesystem traversal or symlink verification.
    """
    return PurePosixPath(path).parts


def owns(claim: str, changed: str) -> bool:
    """Match a whole path component prefix, including an exact match."""
    left, right = claim_parts(claim), claim_parts(changed)
    return right[:len(left)] == left


@dataclass(frozen=True)
class _Claim:
    unit: str
    path: str
    parts: tuple[str, ...]


def _claims(units: list[WorkUnit]) -> list[_Claim]:
    rows = []
    for unit in units:
        if unit.read_only:
            continue
        for path in unit.paths:
            parts = claim_parts(path)
            rows.append(_Claim(unit.id, '/'.join(parts) or '.', parts))
    return rows


def _pair(left: _Claim, right: _Claim) -> tuple[str, str, str, str]:
    return (left.unit, right.unit, left.path, right.path) if left.unit < right.unit else (right.unit, left.unit, right.path, left.path)


def conflicts(units: list[WorkUnit]) -> list[tuple[str, str, str, str]]:
    """Return sorted distinct (left id, right id, left path, right path) overlaps.

    Ignore read-only workers and comparisons within one unit id. Report canonical
    paths. Shared parent directories do not imply overlapping sibling claims.
    Duplicate input ids still block delegation_plan, but do not duplicate rows.
    """
    root = {"claims": [], "children": {}}
    found = set()
    for claim in _claims(units):
        node = root
        related = []
        for part in claim.parts:
            related.extend(node["claims"])
            node = node["children"].setdefault(part, {"claims": [], "children": {}})
        stack = [node]
        while stack:
            below = stack.pop()
            related.extend(below["claims"])
            stack.extend(below["children"].values())
        for other in related:
            if other.unit != claim.unit:
                found.add(_pair(other, claim))
        node["claims"].append(claim)
    return sorted(found)


def delegation_plan(units: list[WorkUnit]) -> dict:
    """Validate owners, proofs, ids, dependencies and exclusive write claims.

    Whitespace-only owners are missing. Every invalid plan is blocked with empty
    waves. Dependency analysis is provided by safe_waves and is already correct.
    """
    ids = [unit.id for unit in units]
    duplicates = sorted({name for name in ids if ids.count(name) > 1})
    missing_owner = sorted({unit.id for unit in units if not unit.owner.strip()})
    missing_proof = sorted({unit.id for unit in units if not unit.proof.strip()})
    overlap = conflicts(units)
    waves, issues = safe_waves(units)
    blocked = bool(duplicates or missing_owner or missing_proof or overlap or issues)
    return {"status": "blocked" if blocked else "ready", "duplicate_ids": duplicates,
            "missing_owner": missing_owner, "missing_proof": missing_proof,
            "conflicts": overlap, "issues": issues, "waves": [] if blocked else waves}
