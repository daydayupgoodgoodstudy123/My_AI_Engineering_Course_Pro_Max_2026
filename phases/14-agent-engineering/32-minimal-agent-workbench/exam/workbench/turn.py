"""One turn of the builder agent on the workbench files."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .files import BOARD_FILE, STATE_FILE, AgentState, Task, load_board, load_state, save_board, save_state

Runner = Callable[[str], int]  # runs one acceptance command and returns its exit code


def run_one_turn(state: AgentState, board: list[Task], run: Runner) -> tuple[AgentState, list[Task]]:
    """Advance the builder by one step, as the lesson's turn does, and return the state and board.

    With no active task, the builder takes back a task of its own that is still in_progress (a
    session that died after writing the board but before writing the state leaves one behind),
    and otherwise pulls the first builder task that is todo and sets it in_progress. Either way
    the task starts with no touched files and no blockers. With nothing to take, the turn is
    idle and next_action says "no work on the board, idle".

    With an active task, the builder touches app.py, then test_app.py, one per turn. The turn
    after that applies the definition of done from AGENTS.md: every acceptance command runs once,
    in order, through run(command), which returns the exit code, and task.checks records each
    code. The task is done when it has at least one command and every one exited 0. Otherwise it
    is blocked, and state.blockers lists "<command> exited <code>" for every failing command, or
    "<id> has no acceptance command". Done or blocked, the task is no longer active and
    touched_files is emptied.
    """
    if state.active_task_id is None:
        nxt = next((t for t in board if t.owner == "builder" and t.status == "todo"), None)
        if nxt is None:
            state.next_action = "no work on the board, idle"
            return state, board
        nxt.status = "in_progress"
        state.active_task_id = nxt.id
        state.touched_files = []
        state.blockers = []
        state.next_action = f"start work on {nxt.id}: {nxt.goal}"
        return state, board

    active = next((t for t in board if t.id == state.active_task_id), None)
    if active is None:
        state.active_task_id = None
        state.next_action = "active task missing from board; resetting and picking new work"
        return state, board
    if "app.py" not in state.touched_files:
        state.touched_files.append("app.py")
        state.next_action = f"add test for {active.id} acceptance"
        return state, board
    if "test_app.py" not in state.touched_files:
        state.touched_files.append("test_app.py")
        state.next_action = f"run verification command for {active.id}"
        return state, board

    exits = {command: run(command) for command in active.acceptance}
    active.checks.update(exits)
    state.active_task_id = None
    state.touched_files = []
    if all(exits.values()):
        active.status = "done"
        state.blockers = []
        state.next_action = "pick next task from board"
    else:
        active.status = "blocked"
        state.blockers = [f"{command} exited {code}" for command, code in exits.items() if code]
        state.next_action = f"{active.id} is blocked: {state.blockers[0]}"
    return state, board


def take_turn(root: Path, run: Runner) -> tuple[AgentState, list[Task]]:
    """Run one turn on the workbench in root and return the new state and board.

    The turn reads agent_state.json and task_board.json, runs run_one_turn, and writes the board
    first and the state second. A session that dies between the two writes therefore leaves its
    task in progress on the board, where the next turn takes it back.
    """
    state = load_state(root / STATE_FILE)
    board = load_board(root / BOARD_FILE)
    state, board = run_one_turn(state, board, run)
    save_board(root / BOARD_FILE, board)
    save_state(root / STATE_FILE, state)
    return state, board
