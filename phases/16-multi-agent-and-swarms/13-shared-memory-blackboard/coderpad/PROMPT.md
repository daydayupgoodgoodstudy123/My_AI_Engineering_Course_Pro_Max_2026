# Shared Memory and Blackboard Patterns — interview coding slice

Original practice · 45-minute suggested upper limit · Python 3.10+ · stdlib only.
This is not an Edison Scientific question or official hiring rubric.

## Scenario

You maintain the `13-shared-memory-blackboard` component. Complete its core `compact_memory` operation,
then implement the independent `cache_replay` extension if time remains.
The scope is intentionally one implementable slice of the lesson; no full model, training run,
cloud service, filesystem deployment, provider API, or GPU integration is required.

## Core

```python
compact_memory(records, limit)
```

Records have id, timestamp, text. Keep the most recent record per id (later input wins timestamp ties), then retain limit records by descending timestamp and lexicographic id ties. Return copied records. limit exact nonnegative int; invalid limit raises ValueError.

## Bonus

```python
cache_replay(events, ttl)
```

Events have op put/get, key(str), time(number), plus value for put. ttl>=0 else ValueError. Put expiry=time+ttl. Return values for get events, None when absent or time>=expiry. Values are JSON-compatible and copied. Unknown op raises ValueError. Events are chronological.

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
