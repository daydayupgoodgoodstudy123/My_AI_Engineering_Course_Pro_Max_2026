# A policy-enforcing tool gateway

Original interview simulation · 45 minutes · Python 3.10+ · standard library only.
This is independent practice, not an Edison Scientific question or scoring policy.

## Scenario

A gateway must enforce policy before forwarding a tool call to an upstream peer.

## Candidate work

Edit only `starter/main.py`. Keep public signatures and supplied helpers intact.
`tests/test_exam.py` and fixtures are provided. You may add your own tests in a new `tests/test_candidate.py`.
Explain your plan briefly, then implement the core before attempting the bonus.

## Core contract

Gateway(routes,fetch,forward): routes maps public names to {'peer':str,'local':str,'roles':set,'pin':str}; fetch(peer,local) returns a current digest string; forward(peer,local,args) executes. call(public,roles,args) checks in order: unknown public raises KeyError; no intersection between caller roles and route roles raises PermissionError; current digest different from pin raises ValueError. Only after these checks, call forward exactly once and return its value. Exceptions from fetch or forward propagate. Rejected calls must never forward; authorization rejection must not even fetch. No cache is used.

## Bonus contract

visible(roles) returns sorted public names whose role set intersects caller roles. It does not fetch or forward anything.

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
