"""The three files of the minimal workbench: AGENTS.md, agent_state.json and task_board.json."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

AGENTS_FILE = "AGENTS.md"
STATE_FILE = "agent_state.json"
BOARD_FILE = "task_board.json"

STATUSES = ("todo", "in_progress", "done", "blocked")
OWNERS = ("builder", "reviewer", "human")

AGENTS_MD = """# AGENTS.md

This repo runs with a workbench. Read these before acting:

1. `agent_state.json` — where the last session stopped.
2. `task_board.json` — what is in flight, what is next.
3. `docs/agent-rules.md` — startup, scope, definition of done (load on demand).

Definition of done: the task referenced by `agent_state.active_task_id` has
`status == "done"` on `task_board.json` and the verification command listed in
its `acceptance` has exited 0.

Verification command: `python3 -m pytest -x`
""".lstrip()


@dataclass
class AgentState:
    """Where the builder is. extra holds the keys this version does not know."""

    active_task_id: str | None
    touched_files: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    next_action: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Task:
    """One task on the board.

    checks holds the exit code of each acceptance command from the last time it ran. extra holds
    the keys this version does not know (priority, depends_on, parent and whatever comes next).
    """

    id: str
    goal: str
    owner: str
    acceptance: list[str]
    status: str = "todo"
    checks: dict[str, int] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)


STATE_KEYS = ("active_task_id", "touched_files", "assumptions", "blockers", "next_action")
TASK_KEYS = ("id", "goal", "owner", "acceptance", "status", "checks")


def write_initial(root: Path) -> None:
    """Lay down the three files in root, leaving alone any that already exist."""
    root.mkdir(parents=True, exist_ok=True)
    if not (root / AGENTS_FILE).exists():
        (root / AGENTS_FILE).write_text(AGENTS_MD, encoding="utf-8")
    if not (root / STATE_FILE).exists():
        save_state(root / STATE_FILE, AgentState(active_task_id=None))
    if not (root / BOARD_FILE).exists():
        save_board(
            root / BOARD_FILE,
            [
                Task(
                    "T-001",
                    "add input validation to /signup",
                    "builder",
                    ["pytest test_app.py::test_signup_rejects_short_password"],
                ),
                Task(
                    "T-002",
                    "document the new /signup contract",
                    "builder",
                    ["grep -q /signup docs/api.md"],
                ),
            ],
        )


def load_state(path: Path) -> AgentState:
    """Read agent_state.json.

    Keys this version does not know (a newer workbench's last_run, say) are kept in extra, so
    that save_state writes them back unchanged.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    return AgentState(**raw)


def save_state(path: Path, state: AgentState) -> None:
    """Write agent_state.json: the lesson's keys in order, then the extra keys as they were read."""
    doc = {key: getattr(state, key) for key in STATE_KEYS}
    doc.update(state.extra)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def task_from_doc(doc: dict[str, Any]) -> Task:
    """Build a Task from one board entry. Keys this version does not know go to extra."""
    known = {key: doc[key] for key in TASK_KEYS if key in doc}
    return Task(**known, extra={k: v for k, v in doc.items() if k not in TASK_KEYS})


def task_to_doc(task: Task) -> dict[str, Any]:
    """The board entry for a task: the known keys in order, then the extra keys as they were read."""
    doc = {key: getattr(task, key) for key in TASK_KEYS}
    doc.update(task.extra)
    return doc


def load_board(path: Path) -> list[Task]:
    """Read task_board.json, a JSON array of tasks in board order, and check it."""
    board = [task_from_doc(doc) for doc in json.loads(path.read_text(encoding="utf-8"))]
    check_board(board)
    return board


def save_board(path: Path, board: list[Task]) -> None:
    """Check the board, then write task_board.json."""
    check_board(board)
    text = json.dumps([task_to_doc(task) for task in board], indent=2)
    path.write_text(text + "\n", encoding="utf-8")


def check_board(board: list[Task]) -> None:
    """Correct supplied validator. Refuse a board the workbench cannot run on, with a ValueError that names the task.

    Statuses and owners come from the lesson's sets, task ids are unique, and the builder has at
    most one task in progress: the one agent_state.json points at, or one that a session which
    died left behind.
    """
    seen: set[str] = set()
    for task in board:
        if task.status not in STATUSES:
            raise ValueError(f"{task.id}: unknown status {task.status!r}")
        if task.owner not in OWNERS:
            raise ValueError(f"{task.id}: unknown owner {task.owner!r}")
        if task.id in seen:
            raise ValueError(f"task id {task.id} appears more than once")
        seen.add(task.id)
    working = [t.id for t in board if t.owner == "builder" and t.status == "in_progress"]
    if len(working) > 1:
        raise ValueError(f"the builder has {len(working)} tasks in progress: {', '.join(working)}")
