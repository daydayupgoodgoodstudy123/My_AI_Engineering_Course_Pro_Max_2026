# Deep Q-Networks (DQN) — interview coding slice

Original practice · 45-minute suggested upper limit · Python 3.10+ · stdlib only.
This is not an Edison Scientific question or official hiring rubric.

## Scenario

You maintain the `05-dqn` component. Complete its core `q_update` operation,
then implement the independent `clip_gradients` extension if time remains.
The scope is intentionally one implementable slice of the lesson; no full model, training run,
cloud service, filesystem deployment, provider API, or GPU integration is required.

## Core

```python
q_update(current, reward, next_values, alpha, gamma, terminal=False)
```

Require alpha,gamma in [0,1]. For terminal transition target=reward and next_values may be empty; otherwise require nonempty next_values and target=reward+gamma*max(next_values). Return current+alpha*(target-current). Invalid inputs raise ValueError.

## Bonus

```python
clip_gradients(gradients, maximum)
```

Return gradients scaled together so L2 norm is at most maximum; leave already-small vectors unchanged in value. maximum>=0, otherwise ValueError. Zero and empty vectors are valid.

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
