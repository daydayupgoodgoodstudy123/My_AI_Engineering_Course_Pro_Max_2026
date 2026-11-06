"""task_board.jsonl: the board as JSON Lines, one task per line, so diffs stay clean (Exercise 3)."""
from __future__ import annotations

import json
from pathlib import Path

from .files import Task, check_board, task_from_doc, task_to_doc


class BoardLines:
    """The board in a JSON Lines file, one task per line, in board order.

    A line is json.dumps(task_to_doc(task)) with json's default settings, and every line ends
    with a newline. People and other tools edit the file too, so a line keeps its exact text
    until its own task changes: changing one task rewrites that task's line and no other.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    def save(self, board: list[Task]) -> None:
        """Check the board and write the whole file, one line per task."""
        raise NotImplementedError

    def load(self) -> list[Task]:
        """Read the tasks in file order and check the board. Blank lines are skipped."""
        raise NotImplementedError

    def update(self, task: Task) -> None:
        """Replace the stored task that has task.id with task. An id not in the file is a KeyError.

        The board is checked before anything is written.
        """
        raise NotImplementedError
