# Compute evaluation metrics and gate a package

Original interview simulation · 45 minutes · Python 3.10+ · standard library only.
This is independent practice, not an Edison Scientific question or scoring policy.

## Scenario

A skill package has excellent trigger recall but failed a safety check. Implement metrics and a release decision that preserves independent evidence layers.

## Candidate work

Edit only `starter/main.py`. Keep public signatures and supplied helpers intact.
`tests/test_exam.py` and fixtures are provided. You may add your own tests in a new `tests/test_candidate.py`.
Explain your plan briefly, then implement the core before attempting the bonus.

## Core contract

metrics(expected,predicted) requires equal-length lists containing exact bool values; otherwise ValueError. Return {'tp','fp','fn','precision','recall'}, using 0.0 when a ratio's denominator is zero. Empty lists are valid.
gate(report,min_precision=.8,min_recall=.8): required fields structure,behavior,safety,portability must each be exactly True. Missing or other values fail. report.metrics must be a dict with numeric precision and recall in [0,1] (bool is invalid); missing/invalid metric contributes reason 'metrics'. Otherwise append 'precision' and/or 'recall' when below thresholds. Return {'ready':not reasons,'reasons':sorted reason strings}. Equality with threshold passes. Thresholds are provided valid. ready applies only to this supplied local evidence; no live-host evidence is inferred.

## Bonus contract

improvement(baseline,with_skill) returns with_skill-baseline; both values must be numeric, non-bool and in [0,1], otherwise ValueError. A negative result is valid evidence, not clamped to zero.

## Commands

```bash
python3 run_tests.py --list
python3 run_tests.py --core
python3 run_tests.py --core -k keyword_from_test_name
python3 run_tests.py --bonus
python3 run_tests.py
```

Read the complete contract before starting. All fixture shapes not declared invalid are supplied valid.
There are no undisclosed external-service requirements. At minute 45, save and record the current result.
Use your own timer; the test runner does not enforce a deadline. Locally stored tests and solutions are readable,
so strict mode relies on your self-discipline or a separate interviewer. Do not read `solution/` or `INTERVIEWER.md` during the attempt.
