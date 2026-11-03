"""Tasks, their messages and artifacts, and every state they have been in, kept in SQLite."""
from __future__ import annotations

import json
import sqlite3

from .model import Artifact, File, Message, Part, Task

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    skill TEXT NOT NULL,
    state TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS history (
    task_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    state TEXT NOT NULL,
    PRIMARY KEY (task_id, seq)
);
CREATE TABLE IF NOT EXISTS messages (
    task_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    role TEXT NOT NULL,
    PRIMARY KEY (task_id, seq)
);
CREATE TABLE IF NOT EXISTS artifacts (
    task_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    mime_type TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS parts (
    task_id TEXT NOT NULL,
    message_seq INTEGER,
    seq INTEGER NOT NULL,
    type TEXT NOT NULL,
    text TEXT,
    name TEXT,
    mime_type TEXT,
    content BLOB,
    data TEXT
);
"""

TABLES = (("tasks", "id"), ("history", "task_id"), ("messages", "task_id"), ("artifacts", "task_id"), ("parts", "task_id"))


class TaskStore:
    """Tasks, their messages and artifacts, and every state they have been in, in one SQLite file.

    Everything comes back exactly as it was saved: the messages in order with their parts in order, a
    file part's name, mimeType and bytes, a data part's keys in their order and every value with its
    type (1 stays an int, 1.0 a float, True a bool), and the whole history, repeated states included.
    A file part's bytes are stored as they are, in one BLOB, not as text and not as base64.
    """

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        self._db.executescript(SCHEMA)

    def save(self, task: Task) -> None:
        """Store the task as it is now. Saving a task again replaces everything stored for it.

        A part of an unknown type raises ValueError, and then nothing is written: the store keeps
        what it had.
        """
        owners = [(seq, message.parts) for seq, message in enumerate(task.messages)]
        if task.artifact is not None:
            owners.append((None, task.artifact.parts))
        rows = [
            (task.id, owner, seq, *_columns(part))
            for owner, parts in owners
            for seq, part in enumerate(parts)
        ]
        with self._db:
            for table, column in TABLES:
                self._db.execute(f"DELETE FROM {table} WHERE {column} = ?", (task.id,))
            self._db.execute(
                "INSERT INTO tasks (id, skill, state) VALUES (?, ?, ?)", (task.id, task.skill, task.state)
            )
            self._db.executemany(
                "INSERT INTO history (task_id, seq, state) VALUES (?, ?, ?)",
                [(task.id, seq, state) for seq, state in enumerate(task.history)],
            )
            self._db.executemany(
                "INSERT INTO messages (task_id, seq, role) VALUES (?, ?, ?)",
                [(task.id, seq, message.role) for seq, message in enumerate(task.messages)],
            )
            if task.artifact is not None:
                self._db.execute(
                    "INSERT INTO artifacts (task_id, name, mime_type) VALUES (?, ?, ?)",
                    (task.id, task.artifact.name, task.artifact.mimeType),
                )
            self._db.executemany(
                "INSERT INTO parts (task_id, message_seq, seq, type, text, name, mime_type, content, data)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )

    def load(self, task_id: str) -> Task:
        """The task as it was last saved. Unknown ids raise KeyError."""
        row = self._db.execute("SELECT skill, state FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise KeyError(task_id)
        history = [
            state
            for (state,) in self._db.execute(
                "SELECT state FROM history WHERE task_id = ? ORDER BY seq", (task_id,)
            )
        ]
        parts: dict[int | None, list[Part]] = {}
        for owner, *columns in self._db.execute(
            "SELECT message_seq, type, text, name, mime_type, content, data FROM parts"
            " WHERE task_id = ? ORDER BY message_seq, seq",
            (task_id,),
        ):
            parts.setdefault(owner, []).append(_part(*columns))
        messages = [
            Message(role, parts.get(seq, []))
            for seq, role in self._db.execute(
                "SELECT seq, role FROM messages WHERE task_id = ? ORDER BY seq", (task_id,)
            )
        ]
        found = self._db.execute(
            "SELECT name, mime_type FROM artifacts WHERE task_id = ?", (task_id,)
        ).fetchone()
        artifact = None if found is None else Artifact(found[0], found[1], parts.get(None, []))
        return Task(task_id, row[0], row[1], history, messages, artifact)

    def task_ids(self, state: str | None = None) -> list[str]:
        """The ids of the stored tasks, sorted, or only of those whose current state is state."""
        if state is None:
            rows = self._db.execute("SELECT id FROM tasks ORDER BY id")
        else:
            rows = self._db.execute("SELECT id FROM tasks WHERE state = ? ORDER BY id", (state,))
        return [task_id for (task_id,) in rows]

    def close(self) -> None:
        self._db.close()


def _columns(part: Part) -> tuple:
    """(type, text, name, mime_type, content, data) for one part."""
    if part.type == "text":
        return ("text", part.text, None, None, None, None)
    if part.type == "file":
        return ("file", None, part.file.name, part.file.mimeType, bytes(part.file.content), None)
    if part.type == "data":
        return ("data", None, None, None, None, json.dumps(part.data))
    raise ValueError(f"unknown part type {part.type!r}")


def _part(kind: str, text, name, mime_type, content, data) -> Part:
    if kind == "text":
        return Part("text", text=text)
    if kind == "file":
        return Part("file", file=File(name, mime_type, content))
    return Part("data", data=json.loads(data))
