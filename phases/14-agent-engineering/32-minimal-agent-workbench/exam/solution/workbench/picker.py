"""What the builder starts next: priorities and dependencies on the board, and a stale state.

Exercises 1 and 2 of the lesson: refuse to run on a state older than 24 hours unless an operator
confirms, and pull the highest-priority todo instead of the first one.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .files import Task

STALE_AFTER = timedelta(hours=24)


@dataclass(frozen=True)
class Decision:
    action: str  # "start", "idle" or "refuse"
    task_id: str | None = None  # the task to start
    waiting: dict[str, list[str]] = field(default_factory=dict)  # idle: todo id -> unfinished deps


def next_task(
    board: list[Task],
    now: datetime,
    last_run: str | None = None,
    confirm: str | None = None,
) -> Decision:
    """Decide what the builder starts next.

    Refuse when the state is stale: last_run (ISO 8601 with a UTC offset, written at the end of
    the last run) is more than 24 hours before now, a timezone-aware datetime. The operator can
    let one stale state through by passing its last_run as confirm. A state that never ran (no
    last_run) is not stale. A last_run without an offset is a ValueError: we don't guess zones.

    Otherwise start the builder's highest-priority todo that is ready; priority is the integer in
    extra["priority"], higher first, 0 when absent, and board order breaks ties. A task is ready
    when every id in extra["depends_on"] belongs to a task that is done. A depends_on id that
    names no task on the board is a ValueError naming it. With nothing to start, the decision is
    idle, and waiting maps every builder todo to its dependencies that are not done yet, in
    depends_on order.
    """
    if last_run is not None:
        moment = datetime.fromisoformat(last_run)
        if moment.tzinfo is None:
            raise ValueError(f"last_run {last_run!r} has no UTC offset")
        if now - moment > STALE_AFTER and confirm != last_run:
            return Decision("refuse")

    by_id = {task.id: task for task in board}
    for task in board:
        for dep in task.extra.get("depends_on", []):
            if dep not in by_id:
                raise ValueError(f"{task.id} depends on {dep}, which is not on the board")

    best: Task | None = None
    waiting: dict[str, list[str]] = {}
    for task in board:
        if task.owner != "builder" or task.status != "todo":
            continue
        pending = [dep for dep in task.extra.get("depends_on", []) if by_id[dep].status != "done"]
        if pending:
            waiting[task.id] = pending
        elif best is None or task.extra.get("priority", 0) > best.extra.get("priority", 0):
            best = task
    if best is not None:
        return Decision("start", best.id)
    return Decision("idle", waiting=waiting)
