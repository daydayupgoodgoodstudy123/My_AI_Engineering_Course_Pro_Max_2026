# Surfaces pair session

Surfaces audits agent workbenches. `surfaces/report.py` holds the lesson's run comparison: a stub agent runs one repo task prompt-only and with the seven workbench surfaces, and a failure-mode report maps each missing surface to its symptom. Audits of real repos score every surface and are appended to a CSV scorecard (`surfaces/scorecard.py`). `surfaces/catch.py` works out which surface stops each failure first and what to add next, `surfaces/monitor.py` watches a run's event log as it arrives, and `surfaces/harness.py` checks a harness description against the lesson's primitives. `surfaces/service.py` wires the scorecard and the catch matrix together for the audit API.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_failure_report`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the run comparison fails.

## Pt 2 `test_scorecard_roundtrip`

Build the audit scorecard.

## Pt 3 `test_catch_matrix`

Find the surface that stops each failure, and the surfaces to add next.

## Pt 4 `test_monitor_stream`

Watch a run's event log as it arrives, and report violations.

## Pt 5 `test_harness_primitives`

Check a harness description against the primitives.
