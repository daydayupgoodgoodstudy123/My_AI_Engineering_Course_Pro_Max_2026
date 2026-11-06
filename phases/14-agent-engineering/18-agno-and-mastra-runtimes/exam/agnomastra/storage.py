"""Composite storage: memory, workflow snapshots and observability events, each in its own backend."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Message:
    session_id: str
    role: str
    content: str


@dataclass(frozen=True)
class Snapshot:
    run_id: str
    status: str
    step: str
    state: dict[str, Any]  # JSON values only


@dataclass(frozen=True)
class Event:
    trace_id: str
    name: str
    ts_ns: int
    attributes: dict[str, Any]  # JSON values only


class CompositeStorage:
    """Routes each record type to its own backend under root:

    memory        root/memory.sqlite3       SQLite, one row per message
    workflows     root/workflows/           one JSON file per run id; saving a run again replaces it
    observability root/observability.log    append-only UTF-8 text, one JSON object per line

    Every record reads back exactly as it was saved, across a close and reopen. Run ids are
    arbitrary strings, and every snapshot file stays inside root/workflows/.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._workflows = self.root / "workflows"
        self._workflows.mkdir(exist_ok=True)
        self._log = self.root / "observability.log"
        self._db = sqlite3.connect(self.root / "memory.sqlite3")
        # TODO: create the memory schema

    # memory ---------------------------------------------------------------
    def add_message(self, message: Message) -> None:
        """Append one message to its session."""
        raise NotImplementedError

    def messages(self, session_id: str) -> list[Message]:
        """One session's messages, in the order they were added."""
        raise NotImplementedError

    # workflows ------------------------------------------------------------
    def save_snapshot(self, snapshot: Snapshot) -> None:
        """Store a run's latest snapshot, replacing any earlier one. An empty run id raises ValueError."""
        raise NotImplementedError

    def load_snapshot(self, run_id: str) -> Snapshot:
        """The latest snapshot saved for run_id. Unknown ids raise KeyError."""
        raise NotImplementedError

    def runs(self) -> list[str]:
        """Every run id with a snapshot, sorted."""
        raise NotImplementedError

    # observability --------------------------------------------------------
    def record(self, event: Event) -> None:
        """Append one event to the log."""
        raise NotImplementedError

    def events(self, trace_id: str | None = None) -> list[Event]:
        """Recorded events in the order they were recorded, optionally for one trace only."""
        raise NotImplementedError

    def close(self) -> None:
        self._db.close()
