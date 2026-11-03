"""Glue used by the CI job: lint a registry, compare it with the release below it, publish it."""
from __future__ import annotations

from .compat import Change, diff_releases
from .releases import ReleaseStore, parse_version
from .rules import lint_registry


class ReleaseRefused(Exception):
    """A release was not published. reasons says why, one line per problem."""

    def __init__(self, reasons: list[str]) -> None:
        super().__init__("; ".join(reasons))
        self.reasons = reasons


class ToolRegistry:
    def __init__(self, store: ReleaseStore) -> None:
        self.store = store

    def previous(self, version: str) -> str | None:
        """The highest published version below version, or None for a first release."""
        key = parse_version(version)
        earlier = [v for v in self.store.versions() if parse_version(v) < key]
        return earlier[-1] if earlier else None

    def release(self, version: str, tools: list[dict]) -> list[Change]:
        """Publish tools as version, and return what changed since the release below it.

        Nothing is published when the registry has a block finding or a change is breaking.
        """
        reasons = [str(f) for f in lint_registry(tools) if f.severity == "block"]
        before = self.previous(version)
        changes = diff_releases(self.store.load(before) if before else [], tools)
        reasons += [f"{c.path}: {c.change} is breaking" for c in changes if c.severity == "breaking"]
        if reasons:
            raise ReleaseRefused(reasons)
        self.store.publish(version, tools)
        return changes
