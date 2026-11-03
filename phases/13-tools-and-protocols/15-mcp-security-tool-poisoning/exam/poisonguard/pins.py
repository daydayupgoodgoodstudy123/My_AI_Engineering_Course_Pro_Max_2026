"""The pin manifest: every approved descriptor digest, in one JSON snapshot file."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class Pin:
    key: str  # qualified name, server.tool
    digest: str  # lowercase hex SHA-256 of the approved descriptor (scanner.descriptor_digest)
    publisher: dict[str, str]  # publisher evidence: registry, package, version, signer, ...
    approved_at: datetime  # timezone-aware
    quarantined_at: datetime | None = None  # timezone-aware; set by a rug pull, cleared by approval


class PinStore:
    """Approved pins, kept in one JSON manifest file.

    Several processes share the manifest: the gateway quarantines pins while it refreshes, and the
    review tool approves them. Every call works on the file as it is now, so no store ever writes
    back a stale copy over another writer's change.
    """

    def __init__(self, path: str | os.PathLike) -> None:
        self.path = Path(path)

    def pins(self) -> dict[str, Pin]:
        """Every pin, keyed by qualified name.

        A manifest that does not exist yet holds no pins. A manifest that cannot be read raises
        ValueError: it must never pass for an empty one.
        """
        raise NotImplementedError

    def get(self, key: str) -> Pin:
        """The pin under a qualified name. Unknown names raise KeyError."""
        raise NotImplementedError

    def approve(self, key: str, digest: str, publisher: dict[str, str], at: datetime) -> Pin:
        """Pin a reviewed descriptor's digest under its qualified name, replacing any earlier pin.

        Qualified names are case-sensitive: notes.Export and notes.export are two different tools.
        The digest is 64 hex digits in either case and is kept lowercase. A key that is not
        server.tool, any other digest, or an approval time without a timezone raises ValueError.
        Approving a quarantined pin again lifts the quarantine.
        """
        raise NotImplementedError

    def quarantine(self, key: str, at: datetime) -> Pin:
        """Quarantine a pin as of `at` (timezone-aware) until it is approved again.

        A pin that is already quarantined keeps the time of its first quarantine.
        Unknown names raise KeyError.
        """
        raise NotImplementedError
