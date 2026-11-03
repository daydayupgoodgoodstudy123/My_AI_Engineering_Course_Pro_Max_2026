"""The admission ledger: an append-only, hash-chained record of every decision.

Each entry holds sequence, time, event, server, version, outcome, reasons, evidence,
previousHash and entryHash. entryHash is digest() of the other nine fields, and previousHash is
the entryHash of the entry before it (GENESIS for the first), so changing any recorded field
breaks that entry and every later link. That makes the ledger tamper-evident, not tamper-proof:
whoever can rewrite the whole chain can make it verify again, so its head is anchored in a
separate trust domain.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any

from .evidence import digest

GENESIS = "GENESIS"


class LedgerError(Exception):
    """The ledger does not verify, or does not hold an anchored head."""


class AdmissionLedger:
    """The ledger in memory. entries is the chain, oldest first."""

    def __init__(self, clock: Callable[[], str]) -> None:
        self.clock = clock
        self.entries: list[dict[str, Any]] = []

    def append(
        self,
        event: str,
        server: str,
        version: str,
        outcome: str,
        reasons: Sequence[str],
        evidence: dict[str, Any],
    ) -> dict[str, Any]:
        """Add one entry after the newest and return a copy of it.

        The entry keeps its own copies of reasons and evidence.
        """
        sequence, previous = self.head()
        body = {
            "sequence": sequence + 1,
            "time": self.clock(),
            "event": event,
            "server": server,
            "version": version,
            "outcome": outcome,
            "reasons": list(reasons),
            "evidence": deepcopy(evidence),
            "previousHash": previous,
        }
        entry = {**body, "entryHash": digest(body)}
        self.entries.append(entry)
        return deepcopy(entry)

    def head(self) -> tuple[int, str]:
        """(sequence, entryHash) of the newest entry; (0, GENESIS) while the ledger is empty.

        This is the value to anchor in a separate trust domain, so it is only handed out for a
        ledger that verifies: a broken chain raises LedgerError.
        """
        if not self.verify():
            raise LedgerError("ledger does not verify")
        if not self.entries:
            return 0, GENESIS
        newest = self.entries[-1]
        return newest["sequence"], newest["previousHash"]

    def verify(self) -> bool:
        """True when every entry, from the first on, has the next sequence number, links to the
        entry before it, and still hashes to its entryHash."""
        previous = GENESIS
        for expected, entry in enumerate(self.entries, start=1):
            body = {key: value for key, value in entry.items() if key != "entryHash"}
            if entry.get("sequence") != expected or entry.get("previousHash") != previous:
                return False
            if entry.get("entryHash") != digest(body):
                return False
            previous = entry["entryHash"]
        return True


class LedgerFile(AdmissionLedger):
    """The admission ledger kept in a JSON-lines file: one entry per line, oldest first.

    Opening reads every entry back and verifies the whole chain; a file that does not verify
    raises LedgerError, and a file that does not exist yet is an empty ledger. anchor is the
    last head() that was stored in a separate trust domain: the file must still hold that entry
    with that hash, or opening raises LedgerError. The chain cannot tell by itself that its
    newest entries were cut off, or that every hash after a change was recomputed; the anchor
    can. A ledger that has grown since the anchor was taken still holds it.

    append writes each new entry to the end of the file as one more line, so the chain carries
    on across reopens.
    """

    def __init__(
        self,
        path: str | Path,
        clock: Callable[[], str],
        anchor: tuple[int, str] | None = None,
    ) -> None:
        raise NotImplementedError

    def append(
        self,
        event: str,
        server: str,
        version: str,
        outcome: str,
        reasons: Sequence[str],
        evidence: dict[str, Any],
    ) -> dict[str, Any]:
        raise NotImplementedError
