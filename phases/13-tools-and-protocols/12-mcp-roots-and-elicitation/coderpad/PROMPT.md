# Constrain paths and consume confirmation

Original interview simulation · 45 minutes · Python 3.10+ · standard library only.
This is independent practice, not an Edison Scientific question or scoring policy.

## Scenario

A destructive workflow asks the user to confirm a candidate set. Enforce filesystem containment and one-time confirmation without deleting files.

## Candidate work

Edit only `starter/main.py`. Keep public signatures and supplied helpers intact.
`tests/test_exam.py` and fixtures are provided. You may add your own tests in a new `tests/test_candidate.py`.
Explain your plan briefly, then implement the core before attempting the bonus.

## Core contract

within(root,candidate) resolves both pathlib paths, following existing symlinks; relative candidates are interpreted relative to root. Return True if resolved candidate equals root or is a descendant, otherwise False. Root exists; resolution errors return False. Do not use string prefix checks.
confirm(action,token,used): allowed actions are accept, decline, cancel; invalid action raises ValueError without consuming token. If token already appears in provided set used, raise ValueError. Otherwise consume it for ALL three outcomes. Return {'status':'confirmed'|'declined'|'canceled','execute':True only for accept}. This function models consumption only; token authentication has already happened upstream. No file deletion.

## Bonus contract

validate_form(data) returns {'title':trimmed} for an exact one-key dict title containing a string of trimmed length 1..40; otherwise raises ValueError.

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
