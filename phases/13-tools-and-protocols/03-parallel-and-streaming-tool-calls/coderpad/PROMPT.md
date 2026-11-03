# Reassemble interleaved tool streams

Original interview simulation · 45 minutes · Python 3.10+ · standard library only.
This is independent practice, not an Edison Scientific question or scoring policy.

## Scenario

A streaming model interleaves argument fragments for several tools. Repair the accumulator without parsing incomplete JSON.

## Candidate work

Edit only `starter/main.py`. Keep public signatures and supplied helpers intact.
`tests/test_exam.py` and fixtures are provided. You may add your own tests in a new `tests/test_candidate.py`.
Explain your plan briefly, then implement the core before attempting the bonus.

## Core contract

1. assemble(events): each event is {'index': nonnegative int, optional 'id': nonempty str, optional 'name': nonempty str, optional 'arguments': str}. Concatenate argument fragments per index in arrival order. id/name may be repeated identically but conflicting values raise ValueError. Indices may arrive out of order; return [{'id', 'name', 'arguments': dict}] ordered by numeric index. Empty events returns [].
2. Parse JSON only after the complete event list is consumed. Missing id/name, missing/invalid/nonobject JSON, duplicate final ids, invalid index (including bool), or invalid fragment types raise ValueError. Do not execute tools in assemble. No mutation of events.

## Bonus contract

parallel(calls, executor, workers=3) uses ThreadPoolExecutor and returns executor(call) results in input order. Each call runs once; independent calls must be able to start concurrently. Executor exceptions propagate. workers is an exact positive int or raises ValueError; empty calls returns []. No wall-clock timing assertions are needed.

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
