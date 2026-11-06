# Speech Recognition (ASR) — CTC, RNN-T, Attention — interview coding slice

Original practice · 45-minute suggested upper limit · Python 3.10+ · stdlib only.
This is not an Edison Scientific question or official hiring rubric.

## Scenario

You maintain the `04-speech-recognition-asr` component. Complete its core `ctc_decode` operation,
then implement the independent `edit_distance` extension if time remains.
The scope is intentionally one implementable slice of the lesson; no full model, training run,
cloud service, filesystem deployment, provider API, or GPU integration is required.

## Core

```python
ctc_decode(tokens, blank=0)
```

Collapse adjacent repeated tokens first, then remove blank tokens. A blank separates repetitions, so [1,0,1] decodes to [1,1]. Tokens and blank are provided scalar ids; empty input returns [].

## Bonus

```python
edit_distance(reference, hypothesis)
```

Return Levenshtein distance between two token lists, using unit insertion/deletion/substitution costs. Inputs are lists of scalar tokens. Empty sequences are valid; no transposition operation.

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
