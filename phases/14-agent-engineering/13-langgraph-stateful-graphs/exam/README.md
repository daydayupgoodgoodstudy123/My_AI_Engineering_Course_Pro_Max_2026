# StateGraph pair session

StateGraph is a small runtime for agents written as stateful graphs. A graph (`stategraph/graph.py`) has nodes that return updates, direct and conditional edges, and reducers that merge each update into the state. The runner (`stategraph/runner.py`) writes a checkpoint after every step, so a run can pause for a human and pick up again after a crash; the checkpoints live in a checkpointer (`stategraph/checkpoint.py`). Each node gets a context (`stategraph/effects.py`) through which it reaches random numbers, the clock and external APIs. `stategraph/sqlite_store.py` keeps checkpoints in a SQLite file, and `stategraph/stream.py` streams a session to the UI.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_pause_and_resume`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the runner fails.

## Pt 2 `test_sqlite_checkpoints`

Keep the checkpoints in a SQLite file.

## Pt 3 `test_record_and_replay`

Record what nodes get from the world, and replay a session from its recording.

## Pt 4 `test_stream_updates`

Stream a session to the UI while it runs.

## Pt 5 `test_nested_subgraphs`

Run graphs inside graphs.
