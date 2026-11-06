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
        check_board(board)
        text = "".join(json.dumps(task_to_doc(task)) + "\n" for task in board)
        self.path.write_text(text, encoding="utf-8")

    def load(self) -> list[Task]:
        """Read the tasks in file order and check the board. Blank lines are skipped."""
        board = [task_from_doc(json.loads(line)) for line in self._lines() if line.strip()]
        check_board(board)
        return board

    def update(self, task: Task) -> None:
        """Replace the stored task that has task.id with task. An id not in the file is a KeyError.

        The board is checked before anything is written.
        """
        lines = self._lines()
        board: list[Task] = []
        position = None
        for index, line in enumerate(lines):
            if not line.strip():
                continue
            stored = task_from_doc(json.loads(line))
            if stored.id == task.id:
                position, stored = index, task
            board.append(stored)
        if position is None:
            raise KeyError(task.id)
        check_board(board)
        lines[position] = json.dumps(task_to_doc(task))
        self.path.write_text("\n".join(lines), encoding="utf-8")

    def _lines(self) -> list[str]:
        # Split on "\n" only: the last item is "" when the file ends with a newline, so joining
        # the items with "\n" gives back the same text.
        return self.path.read_text(encoding="utf-8").split("\n")
