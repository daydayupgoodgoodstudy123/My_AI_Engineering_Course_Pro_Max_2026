"""A content-addressed store for pinned app snapshots."""
from __future__ import annotations

from pathlib import Path
from typing import Any


class SnapshotError(Exception):
    """A stored snapshot no longer matches its digest."""


class SnapshotStore:
    """App snapshots stored by content, one file per distinct snapshot.

    A snapshot's canonical form is its JSON with object keys sorted, no whitespace between
    tokens, and non-ASCII text written as UTF-8 rather than \\u escapes. List order is kept:
    the catalog order is part of the state. The digest is the hex SHA-256 of those bytes,
    and the file <root>/<digest>.json holds exactly those bytes.

    Prices, totals and quantities are integers (bool is not); prices and totals are 0 or
    more and quantities 1 or more.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, state: dict[str, Any]) -> str:
        """Validate and store a snapshot, and return its digest.

        A snapshot that breaks the rules above raises ValueError. Storing an equal snapshot
        again returns the same digest and adds no file.
        """
        raise NotImplementedError

    def get(self, digest: str) -> dict[str, Any]:
        """Load the snapshot stored under digest.

        An unknown digest raises KeyError. The file's bytes are hashed again, and
        SnapshotError, naming the digest, is raised when they no longer hash to it.
        """
        raise NotImplementedError
