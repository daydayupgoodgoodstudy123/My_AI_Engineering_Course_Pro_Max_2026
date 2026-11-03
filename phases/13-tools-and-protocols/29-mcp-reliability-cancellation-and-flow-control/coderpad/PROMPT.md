# Bound progress without losing results

Original interview simulation · 45 minutes · Python 3.10+ · standard library only.
This is independent practice, not an Edison Scientific question or scoring policy.

## Scenario

A slow consumer lets progress events flood its buffer. Implement bounded flow control that preserves final results.

## Candidate work

Edit only `starter/main.py`. Keep public signatures and supplied helpers intact.
`tests/test_exam.py` and fixtures are provided. You may add your own tests in a new `tests/test_candidate.py`.
Explain your plan briefly, then implement the core before attempting the bonus.

## Core contract

Buffer(capacity) requires an exact positive int or raises ValueError. items initially []. push(kind,value) supports only 'progress' and 'final', otherwise ValueError. If full, remove the oldest progress entry anywhere in items before appending the new entry {'kind':kind,'value':value}. If full with only final entries, a new progress is silently dropped (return False) and a new final raises BufferError without mutation. Otherwise append and return True. drain() returns all entries in order and clears the queue.
retry(side_effect,key) returns 'safe' when side_effect is False, 'deduplicated' for side effects with a nonempty string key, and 'unsafe' otherwise. This classification alone does not implement a durable deduplication ledger.

## Bonus contract

Race starts state='running'. cancel() changes running -> canceled and returns True, otherwise False. complete(value) changes running -> completed, saves value, and returns True; otherwise False with no mutation. First terminal event wins. No threads are required.

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
