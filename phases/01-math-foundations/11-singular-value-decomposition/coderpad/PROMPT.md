# Singular Value Decomposition — interview coding slice

Original practice · 45-minute suggested upper limit · Python 3.10+ · stdlib only.
This is not an Edison Scientific question or official hiring rubric.

## Scenario

You maintain the `11-singular-value-decomposition` component. Complete its core `eigenvalues_2x2` operation,
then implement the independent `solve_2x2` extension if time remains.
The scope is intentionally one implementable slice of the lesson; no full model, training run,
cloud service, filesystem deployment, provider API, or GPU integration is required.

## Core

```python
eigenvalues_2x2(matrix)
```

Require a 2x2 numeric matrix. Return its two real eigenvalues sorted ascending. A negative discriminant or invalid shape raises ValueError. Repeated eigenvalues appear twice.

## Bonus

```python
solve_2x2(matrix, rhs)
```

Solve A*x=rhs using a 2x2 matrix and two-element rhs. Invalid shapes or abs(det)<1e-12 raises ValueError. Return [x0,x1].

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
