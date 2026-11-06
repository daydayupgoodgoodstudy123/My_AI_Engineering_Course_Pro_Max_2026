# Capstone 04 — Multimodal Document QA (Vision-First PDF, Tables, Charts) — interview coding slice

Original practice · 45-minute suggested upper limit · Python 3.10+ · stdlib only.
This is not an Edison Scientific question or official hiring rubric.

## Scenario

You maintain the `04-multimodal-document-qa` component. Complete its core `patchify` operation,
then implement the independent `token_f1` extension if time remains.
The scope is intentionally one implementable slice of the lesson; no full model, training run,
cloud service, filesystem deployment, provider API, or GPU integration is required.

## Core

```python
patchify(image, patch_size)
```

image is a nonempty rectangular 2D scalar matrix; both dimensions must be divisible by exact positive int patch_size. Return flattened patches in row-major patch order, pixels within each patch row-major. Invalid shape or size raises ValueError.

## Bonus

```python
token_f1(reference, answer)
```

Inputs are token lists; count overlap as multiset intersection. Both empty ->1; exactly one empty ->0. Otherwise return harmonic mean of overlap/len(answer) and overlap/len(reference).

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
