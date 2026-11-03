# Detect descriptor drift

Original interview simulation · 45 minutes · Python 3.10+ · standard library only.
This is independent practice, not an Edison Scientific question or scoring policy.

## Scenario

A previously approved tool changed its description after discovery. Build deterministic admission findings from pinned descriptors.

## Candidate work

Edit only `starter/main.py`. Keep public signatures and supplied helpers intact.
`tests/test_exam.py` and fixtures are provided. You may add your own tests in a new `tests/test_candidate.py`.
Explain your plan briefly, then implement the core before attempting the bonus.

## Core contract

fingerprint(tool) is SHA256 hex of UTF-8 JSON using sort_keys=True, separators=(',',':'), ensure_ascii=False. All descriptor fields participate; dict key order does not matter, list order does.
scan(catalog,approved) receives peer -> list of descriptors with nonempty name and string description. Public names are peer+'::'+name (delimiter-free names are provided). approved maps public names to digest. Return sorted unique (public_name,code) tuples: code 'unapproved' if absent from approved; 'drift' if digest differs; 'poisoning' if casefolded description contains 'ignore previous', 'send secrets', or 'override policy'; 'collision' for duplicated public names. Findings accumulate independently. No findings for removed approved entries. These three phrase checks are a teaching heuristic, not a complete security detector.

## Bonus contract

admitted(catalog,approved) returns sorted public names having no scan findings; never alter approved.

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
