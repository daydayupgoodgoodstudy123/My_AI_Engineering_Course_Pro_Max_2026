# Resources, prompts, and private caches

Original interview simulation · 45 minutes · Python 3.10+ · standard library only.
This is independent practice, not an Edison Scientific question or scoring policy.

## Scenario

A resource cache leaked one user's context to another. Repair keying and expiry, then implement a small prompt surface.

## Candidate work

Edit only `starter/main.py`. Keep public signatures and supplied helpers intact.
`tests/test_exam.py` and fixtures are provided. You may add your own tests in a new `tests/test_candidate.py`.
Explain your plan briefly, then implement the core before attempting the bonus.

## Core contract

Cache.put(principal,uri,value,now,ttl) stores a deep copy under (principal,uri), with expiry=now+ttl. ttl must be >=0 or raise ValueError; now/ttl are provided integers. get(principal,uri,now) returns a deep copy if now < expiry, else None. Different principals and URIs must not collide; None is not used as a stored value.
render(name,args): only name='summarize' is known, otherwise raise KeyError. args must be exactly {'text':nonempty string after trimming}, else ValueError. Return [{'role':'user','content':'Summarize: '+trimmed_text}]. Resource text remains data; no code execution or model call.

## Bonus contract

resource_kind(uri) returns 'resource' for a nonempty notes:// URI suffix, 'ui' for a nonempty ui:// suffix, and raises ValueError otherwise. Prefix matching is case-sensitive; no URI normalization is required.

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
