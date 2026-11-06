# FailTag pair session

FailTag watches agent traces for failure modes. `failtag/trace.py` holds the trace model, and `failtag/detectors.py` tags a finished trace with the five industry-recurring modes (hallucinated actions, scope creep, cascading errors, context loss, tool misuse) plus success hallucination. Tagged traces live in a directory store with a last-known-good baseline (`failtag/store.py`), `failtag/drift.py` gates builds and pages on drift against that baseline, `failtag/online.py` tags traces while their steps arrive, and `failtag/cascade.py` measures how far a failure spread. `failtag/service.py` wires these together for the trace pipeline.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_detectors`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the detectors fail.

## Pt 2 `test_trace_store`

Store tagged traces and the last-known-good baseline.

## Pt 3 `test_drift_and_gate`

Gate the build on mode rates, and page when a mode drifts from the baseline.

## Pt 4 `test_online_syslog`

Tag interleaved traces while their steps arrive, and report each finding as a syslog line.

## Pt 5 `test_cascade_radius`

Measure the cascade radius of each root-cause failure.
