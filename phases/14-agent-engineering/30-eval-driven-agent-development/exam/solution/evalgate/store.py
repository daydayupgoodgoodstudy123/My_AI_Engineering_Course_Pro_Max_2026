"""Eval results kept next to the code's history: one JSON snapshot per commit."""
from __future__ import annotations

import contextlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .harness import CATEGORIES

_SHA = re.compile(r"[0-9a-f]{40}")


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
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, snapshot: Snapshot) -> None:
        """Store a commit's snapshot.

        The sha must be a full commit id (40 lowercase hex digits). An unknown category or a case
        id used twice raises ValueError, and so does a bad sha.
        """
        path = self._path(snapshot.sha)
        cases: dict[str, dict] = {}
        for case in snapshot.cases:
            if case.category not in CATEGORIES:
                raise ValueError(f"case {case.cid!r} has unknown category {case.category!r}")
            if case.cid in cases:
                raise ValueError(f"case id {case.cid!r} appears twice")
            cases[case.cid] = {
                "category": case.category,
                "passed": case.passed,
                "rounds": case.rounds,
                "flaky": case.flaky,
                "reason": case.reason,
            }
        text = json.dumps({"sha": snapshot.sha, "cases": cases}, ensure_ascii=False, indent=2)
        fd, tmp = tempfile.mkstemp(dir=self.root, prefix=f".{snapshot.sha}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text + "\n")
            os.replace(tmp, path)
        except BaseException:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(tmp)
            raise

    def load(self, sha: str) -> Snapshot:
        """Return a commit's snapshot. A commit without one raises KeyError."""
        try:
            data = json.loads(self._path(sha).read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise KeyError(sha) from None
        return Snapshot(
            data["sha"],
            tuple(
                CaseRecord(cid, c["category"], c["passed"], c["rounds"], c["flaky"], c["reason"])
                for cid, c in data["cases"].items()
            ),
        )

    def baseline(self, history: list[str]) -> Snapshot | None:
        """Main's last-known-good: the snapshot of the newest commit in history that has one.

        history lists main's commits newest first, as `git rev-list main` prints them. Commits
        without a snapshot (CI skipped them) are passed over, and snapshots of commits that are
        not in history (pull requests) are never a baseline. None when no commit in history has
        a snapshot.
        """
        for sha in history:
            if self._path(sha).exists():
                return self.load(sha)
        return None

    def _path(self, sha: str) -> Path:
        if not isinstance(sha, str) or not _SHA.fullmatch(sha):
            raise ValueError(f"not a full commit sha: {sha!r}")
        return self.root / f"{sha}.json"
