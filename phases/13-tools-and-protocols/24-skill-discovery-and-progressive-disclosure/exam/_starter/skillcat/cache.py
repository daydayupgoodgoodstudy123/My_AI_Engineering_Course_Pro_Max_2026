"""A JSON snapshot of discovery, so a new session inspects only the packages that changed.

Packages are listed with package_dirs and inspected with inspect_package, as discover_scope does.
"""
from __future__ import annotations

from pathlib import Path

from .discovery import Discovery, Scope


class DiscoveryCache:
    """Discovery results kept in one JSON snapshot file between sessions.

    discover(scope) returns exactly what discover_scope(scope) returns. A package is inspected
    again only when the SHA-256 of its SKILL.md bytes differs from the snapshot, or when the
    snapshot has nothing for it; size and modification time prove nothing. The results always
    carry the scope that discover() was called with. parsed lists, by directory name, the
    packages that the last discover() call inspected.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.parsed: list[str] = []

    def discover(self, scope: Scope) -> Discovery:
        raise NotImplementedError
