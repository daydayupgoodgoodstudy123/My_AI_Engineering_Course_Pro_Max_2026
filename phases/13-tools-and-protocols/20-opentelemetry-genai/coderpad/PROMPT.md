# Summarize a redacted trace

Original interview simulation · 45 minutes · Python 3.10+ · standard library only.
This is independent practice, not an Edison Scientific question or scoring policy.

## Scenario

Observability must retain latency evidence without recording prompt text or secrets by default.

## Candidate work

Edit only `starter/main.py`. Keep public signatures and supplied helpers intact.
`tests/test_exam.py` and fixtures are provided. You may add your own tests in a new `tests/test_candidate.py`.
Explain your plan briefly, then implement the core before attempting the bonus.

## Core contract

redact(value,capture_content=False) recursively copies dicts/lists. Dict keys are strings. If key.casefold() is authorization, token, api_key, or password, replace its WHOLE value with '[REDACTED]' regardless of opt-in. If capture_content is False, do the same for prompt, completion, content. Other values remain unchanged; input must not mutate.
summarize(spans) receives dicts with name,start,end (numeric milliseconds). If any end<start raise ValueError. Return a dict mapping each name to {'count':n,'total_ms':sum(end-start),'max_ms':maximum duration}. Empty spans returns {}. This is per-span aggregation, not wall-clock trace duration or real OTel export.

## Bonus contract

critical_span(spans) returns the name of the longest individual span; ties choose lexicographically smallest name. Empty spans returns None; span times are valid.

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
