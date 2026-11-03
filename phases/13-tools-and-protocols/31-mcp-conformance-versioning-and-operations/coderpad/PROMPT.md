# Gate a release on complete evidence

Original interview simulation · 45 minutes · Python 3.10+ · standard library only.
This is independent practice, not an Edison Scientific question or scoring policy.

## Scenario

An SDK normalizer hides malformed responses. Validate raw result discriminators, compare preserved fields, and gate a local release report.

## Candidate work

Edit only `starter/main.py`. Keep public signatures and supplied helpers intact.
`tests/test_exam.py` and fixtures are provided. You may add your own tests in a new `tests/test_candidate.py`.
Explain your plan briefly, then implement the core before attempting the bonus.

## Core contract

compare(raw,sdk,capabilities) accepts resultType 'complete' always; 'input_required' only with capability 'input'; 'task' only with capability 'tasks'. Missing/unknown/unauthorized resultType raises ValueError. raw and sdk are dicts. sdk must contain and equal every raw field except raw keys starting 'x-' (optional extensions may be dropped). Equality uses canonical JSON, so True must not equal 1. Extra sdk fields are allowed. Return True on success. Unknown additive raw fields not starting x- must be preserved.
release(report): report.transcripts must be a nonempty list of exact True values; report.redacted and report.rollback_tested must each be exactly True; report.health must be a dict with requests exact int >0, errors exact int 0<=errors<=requests, p95_ms numeric non-bool >=0. Valid health passes only if errors/requests<=.01 and p95_ms<=500. Return {'ready':bool,'reasons':sorted list among transcripts,redacted,rollback,health}. Missing fields fail. This checks supplied local evidence only, not a live production release.

## Bonus contract

failure_rate(report) returns health.errors/health.requests for exact int counts with requests>0 and 0<=errors<=requests, otherwise ValueError.

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
