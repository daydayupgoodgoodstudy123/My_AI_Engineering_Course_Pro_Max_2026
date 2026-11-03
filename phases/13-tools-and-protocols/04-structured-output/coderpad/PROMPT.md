# A typed extraction boundary

Original interview simulation · 45 minutes · Python 3.10+ · standard library only.
This is independent practice, not an Edison Scientific question or scoring policy.

## Scenario

An extraction endpoint must distinguish refusal, parse failure, and schema failure before downstream processing.

## Candidate work

Edit only `starter/main.py`. Keep public signatures and supplied helpers intact.
`tests/test_exam.py` and fixtures are provided. You may add your own tests in a new `tests/test_candidate.py`.
Explain your plan briefly, then implement the core before attempting the bonus.

## Core contract

extract(raw, refusal=None): a non-None refusal takes precedence and returns {'kind':'refusal','reason':refusal}. Otherwise parse the JSON string raw. Invalid JSON returns {'kind':'parse_error'}. Valid data must be a dict with exactly title and score: title is a string trimmed to length 1..80; score has exact type int and is 0..5. Violations return {'kind':'schema_error'}. Success returns {'kind':'ok','value':{'title':trimmed_title,'score':score}}. Never coerce bool, float, string, or null to integer. This is a fixed extraction contract, not a general JSON Schema engine.

## Bonus contract

extract_many(rows) applies extract(raw, refusal) to each row dict, returning {'items':results,'ok_count':number of ok results}. Preserve order; one bad row's raw JSON must not abort other rows. Row envelopes are valid.

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
