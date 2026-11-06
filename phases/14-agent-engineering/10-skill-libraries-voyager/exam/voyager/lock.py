"""Lock a composed skill to one version of every skill it needs, before it is shared."""
from __future__ import annotations

from collections.abc import Mapping, Sequence

# skill name -> version -> that version's dependency references ("name" or "name@v")
Index = Mapping[str, Mapping[int, Sequence[str]]]


class VersionConflict(ValueError):
    """Two skills in one closure pin different versions of the same skill."""


def resolve(index: Index, ref: str) -> list[str]:
    """Lock ref's closure to one version of each skill, dependencies first.

    Read as written, "name@v" means version v and a bare "name" the latest version. Every
    pin in that tree counts: the lock gives each skill the version it is pinned to, or its
    latest version when nothing pins it, so a bare reference follows a pin made anywhere
    else in the tree. Two different pins for one skill raise VersionConflict naming both
    paths from ref, written like "kit@1 -> pickaxe@1 -> sticks@1". An unknown skill or
    version raises KeyError naming the reference ("sticks@3").

    Returns "name@v" for each skill the locked closure reaches, each after the skills it
    depends on, in the order of a depth-first walk that takes dependencies in the order
    they are written.
    """
    raise NotImplementedError
