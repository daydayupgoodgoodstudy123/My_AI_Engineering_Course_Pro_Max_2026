# RTLoop pair session

RTLoop is the real-time core of a small voice agent. Mic audio goes through a ring buffer into 20 ms frames with a level (`rtloop/ring.py`, `rtloop/meter.py`, `rtloop/capture.py`), the latency marks of every turn are kept in SQLite (`rtloop/traces.py`), `rtloop/dialog.py` decides who holds the floor, `rtloop/pipeline.py` runs the stages of the loop, and `rtloop/graph.py` plans the processing graph.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_capture_path`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the capture code fails.

## Pt 2 `test_trace_store`

Keep the latency marks of every turn.

## Pt 3 `test_barge_in`

Let the user cut the assistant off.

## Pt 4 `test_stage_pipeline`

Run the stages of the loop concurrently.

## Pt 5 `test_processing_graph`

Plan the processing graph.
