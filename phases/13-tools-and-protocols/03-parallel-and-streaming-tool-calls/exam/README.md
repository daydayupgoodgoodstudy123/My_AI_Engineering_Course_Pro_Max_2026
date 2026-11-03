# Fanout pair session

Fanout is the part of an agent host that runs a model's tool calls. A model can ask for several calls in one turn and stream their arguments as interleaved fragments. Fanout puts the fragments back together (`fanout/stream.py`), runs the calls at the same time and answers each one under its own id (`fanout/host.py`). `fanout/calllog.py` keeps a crash-recovery log of the calls in flight, `fanout/schedule.py` plans a fan-out that has dependencies and a concurrency limit, `fanout/live.py` streams results while the model is still writing, and `fanout/partial.py` follows a call's arguments before they are complete.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_replay_turn`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the fan-out code fails.

## Pt 2 `test_call_log`

Keep a log of the calls in flight, so that a restarted host runs again only what never got an answer.

## Pt 3 `test_plan_fanout`

Plan a turn whose calls have dependencies and a concurrency limit.

## Pt 4 `test_stream_results`

Stream each result while the model is still writing the turn.

## Pt 5 `test_partial_arguments`

Follow a call's arguments while they are still arriving.
