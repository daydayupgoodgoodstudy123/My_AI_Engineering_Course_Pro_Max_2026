"""A content-addressed store for pinned app snapshots."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class SnapshotError(Exception):
    """A stored snapshot no longer matches its digest."""


def _whole(value: Any, minimum: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def check_state(state: dict[str, Any]) -> None:
    for row in state["catalog"]:
        if not _whole(row["price"], 0):
            raise ValueError(f"price of {row['sku']} must be integer cents, got {row['price']!r}")
    for sku, qty in state["cart"].items():
        if not _whole(qty, 1):
            raise ValueError(f"cart qty of {sku} must be a positive integer, got {qty!r}")
    for order in state["orders"]:
        if not _whole(order["total"], 0):
            raise ValueError(f"total of {order['oid']} must be integer cents, got {order['total']!r}")
        for sku, qty in order["items"].items():
            if not _whole(qty, 1):
                raise ValueError(f"qty of {sku} in {order['oid']} must be a positive integer")


def canonical_bytes(state: dict[str, Any]) -> bytes:
    return json.dumps(state, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


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
        check_state(state)
        data = canonical_bytes(state)
        digest = hashlib.sha256(data).hexdigest()
        path = self.root / f"{digest}.json"
        if not path.exists():
            path.write_bytes(data)
        return digest

    def get(self, digest: str) -> dict[str, Any]:
        """Load the snapshot stored under digest.

        An unknown digest raises KeyError. The file's bytes are hashed again, and
        SnapshotError, naming the digest, is raised when they no longer hash to it.
        """
        path = self.root / f"{digest}.json"
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            raise KeyError(digest) from None
        if hashlib.sha256(data).hexdigest() != digest:
            raise SnapshotError(f"snapshot {digest} does not match its digest")
        return json.loads(data.decode("utf-8"))
