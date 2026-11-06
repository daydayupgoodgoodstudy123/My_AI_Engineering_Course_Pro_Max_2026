# SlicePick pair session

SlicePick chooses a small workflow that can change a product decision. Candidates must cover the required proof before their value, effort and consequence are compared. The service preserves the evidence behind a selection, checks false minimums, watches a controlled pilot and finds missing workflow nodes.

The goal is to make every test in `tests/test_parts.py` pass as written. **Time: 60 minutes.** Use only the standard library and local deterministic data.

## Pt 0 Setup

You need Python 3.10+ and pytest. In a temporary practice copy run `python -B -m pytest -q -p no:cacheprovider`. Every part starts skipped. Remove only the current test's skip marker, keep every test and assertion unchanged.

## Pt 1 `test_slice_decision`

Repair proof-first scoring and decision identity. Preserve the wide-proof timing assertion and all raw report evidence.

## Pt 2 `test_decision_snapshot`

Implement the typed JSON decision snapshot. The atomic file replacement helper is supplied.

## Pt 3 `test_false_minimums_and_stop_rule`

Audit designs relative to the actual proof need and require an effective predeclared stop rule before scoring.

## Pt 4 `test_pilot_stop_stream`

Stream pilot measurements and stop on consecutive errors. The supplied SSE encoder matches the test parser.

## Pt 5 `test_vertical_workflow_completion`

Find the smallest missing connected trigger-to-outcome path in a supplied finite workflow DAG.
