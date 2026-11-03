"""Find the skill packages of each configured scope, then apply the host's collision policy."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Union

from .frontmatter import DiscoveryError, parse_frontmatter

NAME_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
MAX_NAME_CHARS = 64
MAX_DESCRIPTION_CHARS = 1024


@dataclass(frozen=True)
class Scope:
    """A configured skill root. rank is host policy: the lower rank wins a collision."""

    name: str
    root: Path
    rank: int


@dataclass(frozen=True)
class SkillCandidate:
    """A package that passed validation, before collision policy. source is its directory."""

    name: str
    description: str
    scope: str
    rank: int
    source: Path
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Rejection:
    """A package that discovery found but will not publish, and why."""

    scope: str
    path: Path
    reason: str


@dataclass(frozen=True)
class Discovery:
    candidates: tuple[SkillCandidate, ...]
    rejected: tuple[Rejection, ...]


def package_dirs(root: Path) -> list[Path]:
    """The skill packages under a scope root, sorted by directory name.

    A package is an immediate child directory of the root that holds a SKILL.md. A SKILL.md
    deeper inside a package (an example, a template, a test fixture) belongs to that package
    and is never published on its own.
    """
    if not root.is_dir():
        return []
    return sorted(skill_md.parent for skill_md in root.rglob("SKILL.md"))


def inspect_package(scope: Scope, directory: Path) -> Union[SkillCandidate, Rejection]:
    """Validate one package directory: a candidate, or a rejection that says why."""
    skill_md = directory / "SKILL.md"
    if skill_md.is_symlink():
        return Rejection(scope.name, directory, "SKILL.md is a symlink")
    try:
        fields = parse_frontmatter(skill_md)
    except (DiscoveryError, UnicodeDecodeError) as error:
        return Rejection(scope.name, directory, str(error))
    name, description = fields["name"], fields["description"]
    if len(name) > MAX_NAME_CHARS or not NAME_PATTERN.fullmatch(name):
        return Rejection(scope.name, directory, f"name {name!r} is not portable kebab-case")
    if name != directory.name:
        return Rejection(scope.name, directory, f"name {name!r} does not match the directory {directory.name!r}")
    if len(description) > MAX_DESCRIPTION_CHARS:
        return Rejection(scope.name, directory, f"description is longer than {MAX_DESCRIPTION_CHARS} characters")
    metadata = fields.get("metadata", {})
    return SkillCandidate(name, description, scope.name, scope.rank, directory, tuple(sorted(metadata.items())))


def discover_scope(scope: Scope) -> Discovery:
    """Discover one scope. A package that fails validation is rejected; it never stops discovery."""
    candidates: list[SkillCandidate] = []
    rejected: list[Rejection] = []
    for directory in package_dirs(scope.root):
        found = inspect_package(scope, directory)
        if isinstance(found, SkillCandidate):
            candidates.append(found)
        else:
            rejected.append(found)
    return Discovery(tuple(candidates), tuple(rejected))


class CollisionError(ValueError):
    """Packages that share a name at the winning rank: the host will not pick one by accident."""


@dataclass(frozen=True)
class Collision:
    name: str
    winner: SkillCandidate
    shadowed: tuple[SkillCandidate, ...]


def resolve_collisions(
    candidates: Iterable[SkillCandidate],
) -> tuple[tuple[SkillCandidate, ...], tuple[Collision, ...]]:
    """One candidate per name: the one with the lowest rank wins.

    The candidates it shadows stay in the collision record, best rank first. Two candidates
    that share a name at the winning rank raise CollisionError; their paths never decide.
    Winners and collisions are sorted by name.
    """
    grouped: dict[str, list[SkillCandidate]] = {}
    for candidate in candidates:
        grouped.setdefault(candidate.name, []).append(candidate)
    winners: list[SkillCandidate] = []
    collisions: list[Collision] = []
    for name in sorted(grouped):
        options = sorted(grouped[name], key=lambda c: (str(c.source), c.rank))
        top = min(c.rank for c in options)
        tied = [c for c in options if c.rank == top]
        if len(tied) > 1:
            paths = ", ".join(str(c.source) for c in tied)
            raise CollisionError(f"ambiguous {name!r} at rank {top}: {paths}")
        winners.append(options[0])
        if len(options) > 1:
            collisions.append(Collision(name, options[0], tuple(options[1:])))
    return tuple(winners), tuple(collisions)
