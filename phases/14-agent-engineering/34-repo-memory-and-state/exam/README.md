# Statefile pair session

Statefile keeps an agent's working state in files in the repo, so the next session, the next agent and the next reviewer read the same source of truth. `statefile/schema.py` holds the JSON Schemas of `agent_state.json` and `task_board.json` and a small validator, and `statefile/manager.py` loads, validates and writes one state file. `statefile/snapshot.py` is the crash-safe snapshot store the workbench is moving to. `statefile/migrate.py` brings old state files up to the current schema, `statefile/sessions.py` lets several agent sessions share one state file, and `statefile/graph.py` deals with schema versions that branch and merge.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`), on macOS or Linux. Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_state_manager`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the state manager fails. Typed-JSON enum keys and their per-call index are supplied correctly.

## Pt 2 `test_snapshot_durability`

Make state snapshots survive a crash at any point.

## Pt 3 `test_migration_chain`

Bring old state files up to the current schema.

## Pt 4 `test_concurrent_sessions`

Let several sessions share one state file.

## Pt 5 `test_migration_graph`

Find the way through a schema history that branches and merges.
