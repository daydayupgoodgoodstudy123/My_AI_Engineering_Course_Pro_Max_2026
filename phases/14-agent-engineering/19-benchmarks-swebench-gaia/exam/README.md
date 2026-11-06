# swebench pair session

swebench is a small SWE-bench-style evaluation harness for coding agents. `swebench/harness.py` runs a task's tests before and after a candidate patch and gates on FAIL_TO_PASS and PASS_TO_PASS, `swebench/store.py` keeps a run's results in CSV files, `swebench/report.py` reports a run in more than one number, `swebench/stream.py` evaluates an agent on many tasks at once, and `swebench/gaia.py` levels GAIA-style questions. `swebench/service.py` wires the CI job together. There is no real model and no network: the tests drive scripted agents.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_harness_gate`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the harness grades patches wrong.

## Pt 2 `test_result_store`

Store a run's results.

## Pt 3 `test_report_views`

Report the run the way the lesson asks: Verified, SWE-bench+, and percentiles.

## Pt 4 `test_stream_results`

Evaluate many tasks at once and stream the results.

## Pt 5 `test_gaia_levels`

Level GAIA-style questions by their decomposition.
