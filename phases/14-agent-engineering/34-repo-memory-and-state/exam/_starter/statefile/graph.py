"""Migration graphs: schema versions that branch and merge, and shortcut migrations."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .schema import VersionError

Step = tuple[int, int]
Migration = Callable[[dict], dict]


class MigrationGraph:
    """Migrations between schema versions, as a directed acyclic graph.

    Versions are ints, each with a schema. Two teams may bump the schema from the same version
    (1 -> 2 and 1 -> 3) and a later version merge both (2 -> 4 and 3 -> 4); a shortcut
    (1 -> 4) does in one step what a chain does in several. Every migration goes to a higher
    version, so the graph has no cycles.
    """

    def __init__(self, schemas: dict[int, dict[str, Any]]) -> None:
        self.schemas = schemas
        self.edges: dict[int, dict[int, Migration]] = {}

    def add(self, src: int, dst: int, fn: Migration) -> None:
        """Register the migration from src to dst. Like any migration script, fn may change the
        document it is given."""
        if src not in self.schemas or dst not in self.schemas:
            raise VersionError(f"no schema for version {src if src not in self.schemas else dst}")
        if dst <= src:
            raise ValueError("a migration goes to a higher version")
        self.edges.setdefault(src, {})[dst] = fn

    def path(self, start: int, target: int) -> list[Step]:
        """The migrations that take a document from start to target.

        The fewest steps; among equally short paths, the one whose versions, read in order,
        compare smallest as integers. [] when start == target. VersionError when either
        version has no schema, or target cannot be reached from start.
        """
        raise NotImplementedError

    def upgrade(self, doc: dict, target: int) -> dict:
        """Migrate doc to target along path().

        doc is validated against its own version's schema first and every step's result against
        that step's version. The steps work on a copy: the caller's document never changes.
        """
        raise NotImplementedError

    def disagreements(self, doc: dict, target: int) -> list[list[Step]]:
        """Check that every way from doc's version to target gives the same document.

        A shortcut must give what the chain it skips gives. Runs doc along every path to target
        and returns the paths whose result is not == to the result along path(), in order
        (compared version by version as integers); [] when they all agree. Every path starts
        from its own copy of doc.
        """
        raise NotImplementedError
