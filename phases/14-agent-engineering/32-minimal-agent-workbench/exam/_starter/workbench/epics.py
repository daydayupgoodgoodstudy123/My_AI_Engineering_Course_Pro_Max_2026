"""Epics on the board: a task whose extra["parent"] names another task sits under it."""
from __future__ import annotations

from dataclasses import dataclass

from .files import Task


@dataclass(frozen=True)
class Rollup:
    status: dict[str, str]  # every task id -> its rolled-up status
    conflicts: list[tuple[str, str, str]]  # (epic id, status on the board, rolled-up status)
    next_leaf: str | None  # the builder's next task


def roll_up(board: list[Task]) -> Rollup:
    """Read the epics out of the board and say what is up next.

    A task whose extra["parent"] names another task is its child, and a task with children is an
    epic. A parent that names no task on the board, or a chain of parents that comes back round,
    is a ValueError naming the task.

    status gives every task its rolled-up status. A task without children keeps its own. An epic
    is done when every child is done, otherwise blocked when any child is blocked, otherwise
    in_progress when any child is in_progress or done, otherwise todo. Children count with their
    rolled-up status, so epics nest. conflicts lists (id, status on the board, rolled-up status)
    for every epic whose two statuses differ, in board order; the rolled-up one is the truth.

    next_leaf walks the forest depth first, the roots and then each epic's children, taking
    siblings in priority order (extra["priority"], higher first, 0 when absent, board order on
    ties). It returns the first builder task without children whose own status is todo, or None.
    An epic that rolls up as blocked can still hold work.
    """
    raise NotImplementedError
