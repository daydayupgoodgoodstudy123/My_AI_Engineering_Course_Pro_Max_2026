# Building a Tokenizer from Scratch — interview coding slice

Original practice · 45-minute suggested upper limit · Python 3.10+ · stdlib only.
This is not an Edison Scientific question or official hiring rubric.

## Scenario

You maintain the `02-building-a-tokenizer` component. Complete its core `merge_pair` operation,
then implement the independent `ngram_counts` extension if time remains.
The scope is intentionally one implementable slice of the lesson; no full model, training run,
cloud service, filesystem deployment, provider API, or GPU integration is required.

## Core

```python
merge_pair(tokens, pair)
```

pair must contain exactly two strings. Scan tokens left to right, replacing each non-overlapping adjacent match with concatenation. Preserve unmatched tokens. Invalid pair raises ValueError; input lists do not mutate.

## Bonus

```python
ngram_counts(tokens, n)
```

n is exact positive int. Return a dict whose keys are JSON strings encoding each token window (json.dumps defaults) and whose values are counts. n>len(tokens) or empty tokens returns {}. Invalid n raises ValueError.

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
