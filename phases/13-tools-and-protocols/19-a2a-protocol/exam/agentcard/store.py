"""Tasks, their messages and artifacts, and every state they have been in, kept in SQLite."""
from __future__ import annotations

import sqlite3

from .model import Task


class TaskStore:
    """Tasks, their messages and artifacts, and every state they have been in, in one SQLite file.

    Everything comes back exactly as it was saved: the messages in order with their parts in order, a
    file part's name, mimeType and bytes, a data part's keys in their order and every value with its
    type (1 stays an int, 1.0 a float, True a bool), and the whole history, repeated states included.
    A file part's bytes are stored as they are, in one BLOB, not as text and not as base64.
    """

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        # TODO: create the schema

    def save(self, task: Task) -> None:
        """Store the task as it is now. Saving a task again replaces everything stored for it.

        A part of an unknown type raises ValueError, and then nothing is written: the store keeps
        what it had.
        """
        raise NotImplementedError

    def load(self, task_id: str) -> Task:
        """The task as it was last saved. Unknown ids raise KeyError."""
        raise NotImplementedError

    def task_ids(self, state: str | None = None) -> list[str]:
        """The ids of the stored tasks, sorted, or only of those whose current state is state."""
        raise NotImplementedError

    def close(self) -> None:
        self._db.close()
