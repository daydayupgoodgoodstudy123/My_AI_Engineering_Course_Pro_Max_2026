# Validate authorization bindings

Original interview simulation · 45 minutes · Python 3.10+ · standard library only.
This is independent practice, not an Edison Scientific question or scoring policy.

## Scenario

The identity layer already verified a token signature. Enforce issuer, resource, expiry, and scope bindings at the resource boundary.

## Candidate work

Edit only `starter/main.py`. Keep public signatures and supplied helpers intact.
`tests/test_exam.py` and fixtures are provided. You may add your own tests in a new `tests/test_candidate.py`.
Explain your plan briefly, then implement the core before attempting the bonus.

## Core contract

challenge(verifier) returns base64url(SHA256(ASCII verifier)) without '=' padding. Verifier is a provided valid ASCII string.
authorize(claims,issuer,resource,required,now) returns {'ok':True} or {'ok':False,'error':code}. Check in order: iss exactly equals issuer ('issuer'); aud equals resource as a string OR is a list containing resource ('audience'); exp has exact type int and now<exp ('expired'); scope is a space-separated string whose tokens include all required scopes ('scope'). Missing claims fail their respective check. Extra scopes are allowed. No case folding. claims is a dict; required is a set of strings. This is not signature verification or a full OAuth implementation.

## Bonus contract

step_up(current,required) returns a sorted list of missing scopes, where current and required are sets; do not request already granted scopes.

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
