# Drive an agent task lifecycle

Original interview simulation · 45 minutes · Python 3.10+ · standard library only.
This is independent practice, not an Edison Scientific question or scoring policy.

## Scenario

A coordinator delegates work to a fake specialist. Implement a task lifecycle with replay-safe message handling.

## Candidate work

Edit only `starter/main.py`. Keep public signatures and supplied helpers intact.
`tests/test_exam.py` and fixtures are provided. You may add your own tests in a new `tests/test_candidate.py`.
Explain your plan briefly, then implement the core before attempting the bonus.

## Core contract

Task starts status='submitted', seen={}, artifacts=[]. apply(message_id,target,artifact=None) allows submitted -> working or rejected; working -> input-required, completed, failed, canceled; input-required -> working or canceled. A fresh message requesting any other transition raises ValueError without consuming its id. A completed transition requires a nonempty string artifact; no other transition may supply an artifact. On success set status, append artifact if completed, save (target,artifact) under message_id, return status. An exact replay of an accepted message returns CURRENT status without changing artifacts, even if status has since advanced. Reusing a message id with different contents raises ValueError. ids are provided nonempty strings.

## Bonus contract

text_parts(parts) joins text values of {'type':'text','text':str} parts with newline, ignoring file/data parts. Input parts are valid fixture dicts; empty list returns ''.

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
