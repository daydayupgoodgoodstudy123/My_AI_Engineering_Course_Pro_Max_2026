# Bind a continuation to its request

Original interview simulation · 45 minutes · Python 3.10+ · standard library only.
This is independent practice, not an Edison Scientific question or scoring policy.

## Scenario

A continuation token must not be reusable for a different user or tool call. Implement integrity and request binding using the supplied stdlib helpers.

## Candidate work

Edit only `starter/main.py`. Keep public signatures and supplied helpers intact.
`tests/test_exam.py` and fixtures are provided. You may add your own tests in a new `tests/test_candidate.py`.
Explain your plan briefly, then implement the core before attempting the bonus.

## Core contract

seal(state,secret) returns urlsafe-base64(canonical JSON bytes)+'.'+hex HMAC-SHA256 of those bytes. Provided canonical() defines sorted compact JSON. Keep standard base64 padding.
verify(token,secret,principal,method,arguments,now) returns the decoded state dict only if signature matches, state.principal/method/arguments exactly match the supplied values under canonical JSON equality, and expires has exact type int with now < expires. Otherwise raise ValueError, including malformed token/base64/JSON. Expected state keys are principal,method,arguments,expires. This integrity token is not encrypted and does not prevent replay by itself.

## Bonus contract

next_round(current,maximum) returns current+1 when 0<=current<maximum; otherwise raises ValueError. Both values must have exact type int and maximum>0.

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
