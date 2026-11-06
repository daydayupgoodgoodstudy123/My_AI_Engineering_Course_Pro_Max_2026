# Workbench pair session

Workbench is the three-file minimal agent workbench: a short `AGENTS.md` router, `agent_state.json` (where the builder agent is) and `task_board.json` (the queue). `workbench/context.py` loads the root router and requested deeper documents; `workbench/files.py` reads and writes the three files, and `workbench/turn.py` runs one turn of the builder: read the state, take a task from the board, touch one file or run the task's acceptance commands, then write both files back. `workbench/lines.py` is the JSON Lines board the repo is moving to, `workbench/picker.py` chooses what the builder starts next, `workbench/patches.py` tells a watcher what each turn changed, and `workbench/epics.py` reads epics out of the board.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_turn_cycle`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and repair the turn loop and keep deeper documentation loads limited to what this turn requests.

## Pt 2 `test_board_lines`

Keep the board as JSON Lines.

## Pt 3 `test_pick_next`

Choose the builder's next task, and refuse to run on a stale state.

## Pt 4 `test_turn_patches`

Send a watcher what every turn changed, as JSON Patch.

## Pt 5 `test_epic_rollup`

Roll task status up through epics.
