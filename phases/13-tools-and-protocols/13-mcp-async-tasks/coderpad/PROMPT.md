# Persist a task state machine

Original interview simulation · 45 minutes · Python 3.10+ · standard library only.
This is independent practice, not an Edison Scientific question or scoring policy.

## Scenario

A worker restarts between requests. Complete durable task creation and legal transitions using the provided persistence helper.

## Candidate work

Edit only `starter/main.py`. Keep public signatures and supplied helpers intact.
`tests/test_exam.py` and fixtures are provided. You may add your own tests in a new `tests/test_candidate.py`.
Explain your plan briefly, then implement the core before attempting the bonus.

## Core contract

TaskStore(path) loads a JSON dict or starts empty. create(task_id,owner) creates {'id':task_id,'owner':owner,'status':'queued'}, persists it, and returns a copy. Duplicate task id raises ValueError without changing existing state. transition(task_id,owner,status) returns a copied updated record after persisting. Unknown task OR mismatched owner raises KeyError. Allowed transitions: queued -> working or canceled; working -> completed, failed, or canceled. All other transitions, including terminal repeats, raise ValueError with no state change. get(task_id) is provided for inspection. ids and owners are nonempty strings; persistence errors are outside this exercise's fault model. _persist is already supplied.

## Bonus contract

purge_terminal() deletes all completed/failed/canceled records, persists once, returns sorted removed ids, and preserves queued/working tasks.

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
