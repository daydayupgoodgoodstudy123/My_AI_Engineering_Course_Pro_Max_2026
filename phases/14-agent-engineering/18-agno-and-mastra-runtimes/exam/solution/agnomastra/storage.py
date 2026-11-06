"""Composite storage: memory, workflow snapshots and observability events, each in its own backend."""
from __future__ import annotations

import dataclasses
import hashlib
import json
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


MEMORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL
)
"""


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
        with self._db:
            self._db.execute(MEMORY_SCHEMA)

    # memory ---------------------------------------------------------------
    def add_message(self, message: Message) -> None:
        """Append one message to its session."""
        with self._db:
            self._db.execute(
                "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
                (message.session_id, message.role, message.content),
            )

    def messages(self, session_id: str) -> list[Message]:
        """One session's messages, in the order they were added."""
        rows = self._db.execute(
            "SELECT session_id, role, content FROM messages WHERE session_id = ? ORDER BY seq",
            (session_id,),
        )
        return [Message(*row) for row in rows]

    # workflows ------------------------------------------------------------
    def save_snapshot(self, snapshot: Snapshot) -> None:
        """Store a run's latest snapshot, replacing any earlier one. An empty run id raises ValueError."""
        if not snapshot.run_id:
            raise ValueError("run_id must not be empty")
        text = json.dumps(dataclasses.asdict(snapshot), ensure_ascii=False)
        self._snapshot_path(snapshot.run_id).write_text(text, encoding="utf-8")

    def load_snapshot(self, run_id: str) -> Snapshot:
        """The latest snapshot saved for run_id. Unknown ids raise KeyError."""
        path = self._snapshot_path(run_id)
        if not path.exists():
            raise KeyError(run_id)
        return Snapshot(**json.loads(path.read_text(encoding="utf-8")))

    def runs(self) -> list[str]:
        """Every run id with a snapshot, sorted."""
        return sorted(
            json.loads(path.read_text(encoding="utf-8"))["run_id"]
            for path in self._workflows.glob("*.json")
        )

    def _snapshot_path(self, run_id: str) -> Path:
        return self._workflows / (hashlib.sha256(run_id.encode("utf-8")).hexdigest() + ".json")

    # observability --------------------------------------------------------
    def record(self, event: Event) -> None:
        """Append one event to the log."""
        line = json.dumps(dataclasses.asdict(event), ensure_ascii=False) + "\n"
        with open(self._log, "a", encoding="utf-8", newline="\n") as log:
            log.write(line)

    def events(self, trace_id: str | None = None) -> list[Event]:
        """Recorded events in the order they were recorded, optionally for one trace only."""
        if not self._log.exists():
            return []
        lines = self._log.read_text(encoding="utf-8").split("\n")
        events = [Event(**json.loads(line)) for line in lines if line]
        return [e for e in events if trace_id is None or e.trace_id == trace_id]

    def close(self) -> None:
        self._db.close()
