# Video-Language Models: Temporal Tokens and Grounding — interview coding slice

Original practice · 45-minute suggested upper limit · Python 3.10+ · stdlib only.
This is not an Edison Scientific question or official hiring rubric.

## Scenario

You maintain the `17-video-language-temporal-grounding` component. Complete its core `sample_frames` operation,
then implement the independent `box_iou` extension if time remains.
The scope is intentionally one implementable slice of the lesson; no full model, training run,
cloud service, filesystem deployment, provider API, or GPU integration is required.

## Core

```python
sample_frames(length, count)
```

Require exact nonnegative integers length/count and count<=length. Return count indices spanning 0..length-1 using floor(i*(length-1)/(count-1)). count=0 -> []; count=1 -> [0]. Invalid input raises ValueError.

## Bonus

```python
box_iou(a, b)
```

Boxes are [x1,y1,x2,y2], with x2>=x1 and y2>=y1; reject other shapes/reversed bounds with ValueError. Return intersection area / union area, or 0 if union is zero. Touching edges have zero intersection.

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
