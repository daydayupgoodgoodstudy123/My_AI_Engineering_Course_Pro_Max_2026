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
    by_id = {task.id: task for task in board}
    children: dict[str, list[Task]] = {task.id: [] for task in board}
    roots: list[Task] = []
    for task in board:
        parent = task.extra.get("parent")
        if parent is None:
            roots.append(task)
        elif parent not in by_id:
            raise ValueError(f"{task.id}: parent {parent} is not on the board")
        else:
            children[parent].append(task)

    rolled: dict[str, str] = {}

    def settle(task: Task) -> str:
        kids = children[task.id]
        if not kids:
            rolled[task.id] = task.status
            return task.status
        below = [settle(kid) for kid in kids]
        if all(s == "done" for s in below):
            result = "done"
        elif "blocked" in below:
            result = "blocked"
        elif "in_progress" in below or "done" in below:
            result = "in_progress"
        else:
            result = "todo"
        rolled[task.id] = result
        return result

    for root in roots:
        settle(root)
    stranded = [task.id for task in board if task.id not in rolled]
    if stranded:
        raise ValueError(f"{stranded[0]}: its chain of parents comes back round")

    def walk(tasks: list[Task]) -> str | None:
        for task in sorted(tasks, key=lambda t: -t.extra.get("priority", 0)):
            if children[task.id]:
                found = walk(children[task.id])
                if found is not None:
                    return found
            elif task.owner == "builder" and task.status == "todo":
                return task.id
        return None

    return Rollup(
        status={task.id: rolled[task.id] for task in board},
        conflicts=[
            (task.id, task.status, rolled[task.id])
            for task in board
            if children[task.id] and task.status != rolled[task.id]
        ],
        next_leaf=walk(roots),
    )
