# Isolate token and key caches

Original interview simulation · 45 minutes · Python 3.10+ · standard library only.
This is independent practice, not an Edison Scientific question or scoring policy.

## Scenario

Production authorization failures came from a token cache keyed only by user and a stale signing-key cache. Repair these isolated cache boundaries.

## Candidate work

Edit only `starter/main.py`. Keep public signatures and supplied helpers intact.
`tests/test_exam.py` and fixtures are provided. You may add your own tests in a new `tests/test_candidate.py`.
Explain your plan briefly, then implement the core before attempting the bonus.

## Core contract

token_for(cache,issuer,resource,now) looks up tuple (issuer,resource). Return the token record only if exp has exact type int and now<exp; else None. Return a copy. Records contain token and exp; do not reuse another issuer/resource entry.
KeyCache(ttl) has keys={}, expires=0. get(kid,now,fetch) refreshes by calling fetch() once when now>=expires OR kid is absent from cached keys. A successful fetch replaces the entire key map and sets expires=now+ttl. Return keys[kid], raising KeyError if still absent. Fetch errors propagate; do not serve stale keys on refresh failure and do not modify cache on that failure. At most one fetch per get, including unknown kid. fetch returns a dict; ttl>0 and time values are provided valid integers. Cryptographic signature checking is outside this exercise.

## Bonus contract

invalidate(cache,issuer) removes every token cache entry for that issuer and returns the number removed; preserve other issuers.

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
