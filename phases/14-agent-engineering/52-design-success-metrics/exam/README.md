# MetricPlan pair session

MetricPlan turns an outcome goal into reproducible measurements. `contract.py` validates metric contracts and reads a bounded source snapshot, `replays.py` keeps raw observations, `decision.py` applies the predeclared decision, `pilot.py` emits fixed-batch reports, and `gqm.py` traces metrics to questions and goals.

The goal is to write application code so every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_metric_contract_report`

Comment out `@pytest.mark.skip('Part 1')`, run pytest, and find why reproducible measurement reports omit evidence or take too long.

## Pt 2 `test_replay_store_roundtrip`

Keep every raw replay and query the latest evidence without rewriting it.

## Pt 3 `test_predeclared_measurement_decision`

Decide pass, fail or ambiguous from the registered batch and the entire pilot.

## Pt 4 `test_pilot_metric_stream`

Publish complete fixed-batch reports while responding immediately to an unsafe pilot.

## Pt 5 `test_goal_question_metric_trace`

Trace shared metrics through the questions and child goals that need them.
