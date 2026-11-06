# RL for Games — AlphaZero, MuZero, and the LLM-Reasoning Era — interview coding slice

Original practice · 45-minute suggested upper limit · Python 3.10+ · stdlib only.
This is not an Edison Scientific question or official hiring rubric.

## Scenario

You maintain the `12-rl-for-games` component. Complete its core `bellman_backup` operation,
then implement the independent `select_ucb` extension if time remains.
The scope is intentionally one implementable slice of the lesson; no full model, training run,
cloud service, filesystem deployment, provider API, or GPU integration is required.

## Core

```python
bellman_backup(actions, gamma)
```

Each action is a nonempty list of [probability,reward,next_value] transitions. Probabilities per action must be nonnegative and sum to 1 within 1e-9. Return max over actions of sum(p*(r+gamma*v)). Require at least one action and gamma in [0,1], else ValueError.

## Bonus

```python
select_ucb(means, visits, total, exploration)
```

means/visits must be same-length nonempty lists; visits are exact nonnegative ints; total exact int >=1, exploration>=0. Return first unvisited index if any; else maximize mean+c*sqrt(log(total)/visits), ties lower index. Invalid input raises ValueError.

## Shared rules and material

- Edit `starter/main.py` and keep both public signatures intact. Inputs must remain unchanged, including on failure.
- Read `fixtures.json` for six core and two bonus examples, plus `tests/test_exam.py` and `_support.py` for the test harness.
- Floating outputs use absolute/relative tolerance 1e-8. Booleans are distinct from integers.
- You may add meaningful tests in a new `tests/test_candidate.py`; keep supplied fixtures/tests intact.
- Only behavior expressly specified here is scored. Exercise simplifications are not claims about live frameworks or protocols.
- The exact kernel may recur in related lessons; `SCOPE.json` identifies core/bonus names. Repeated content is practice, not an unseen test.

## Commands (inside this coderpad directory)

```bash
python3 run_tests.py --list
python3 run_tests.py --core
python3 run_tests.py --core -k 01
python3 run_tests.py --bonus
python3 run_tests.py
```

Use your own timer. At minute 45, save, record the current result, and then review.
Keep `solution/`, `INTERVIEWER.md`, the original lesson implementation and external answer assistance closed during an independent attempt.
The local filesystem cannot actually hide answers or enforce a timer.
