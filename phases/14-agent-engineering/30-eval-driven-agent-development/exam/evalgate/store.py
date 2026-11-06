"""Eval results kept next to the code's history: one JSON snapshot per commit."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .harness import CATEGORIES


@dataclass(frozen=True)
class CaseRecord:
    """One case's result on one commit. flaky is the case's quarantine status when it ran."""

    cid: str
    category: str
    passed: bool
    rounds: int
    flaky: bool
    reason: str


@dataclass(frozen=True)
class Snapshot:
    """Every case's result on one commit, in suite order."""

    sha: str
    cases: tuple[CaseRecord, ...]


class SnapshotStore:
    """One JSON file per commit, <root>/<sha>.json.

    Saving a commit again (a CI re-run) replaces its snapshot. The new file is written next to
    the old one and moved over it with os.replace, so a reader never sees half a snapshot.
    """

    def __init__(self, root: str | os.PathLike) -> None:
        self.root = Path(root)

    def save(self, snapshot: Snapshot) -> None:
        """Store a commit's snapshot.

        The sha must be a full commit id (40 lowercase hex digits). An unknown category or a case
        id used twice raises ValueError, and so does a bad sha.
        """
        raise NotImplementedError

    def load(self, sha: str) -> Snapshot:
        """Return a commit's snapshot. A commit without one raises KeyError."""
        raise NotImplementedError

    def baseline(self, history: list[str]) -> Snapshot | None:
        """Main's last-known-good: the snapshot of the newest commit in history that has one.

        history lists main's commits newest first, as `git rev-list main` prints them. Commits
        without a snapshot (CI skipped them) are passed over, and snapshots of commits that are
        not in history (pull requests) are never a baseline. None when no commit in history has
        a snapshot.
        """
        raise NotImplementedError
