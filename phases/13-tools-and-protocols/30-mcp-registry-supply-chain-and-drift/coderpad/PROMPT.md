# Pin admission and preserve rollback history

Original interview simulation · 45 minutes · Python 3.10+ · standard library only.
This is independent practice, not an Edison Scientific question or scoring policy.

## Scenario

A registry entry is discovery evidence, not approval. Implement a small admission controller driven by independently supplied evidence.

## Candidate work

Edit only `starter/main.py`. Keep public signatures and supplied helpers intact.
`tests/test_exam.py` and fixtures are provided. You may add your own tests in a new `tests/test_candidate.py`.
Explain your plan briefly, then implement the core before attempting the bonus.

## Core contract

Registry(namespace) starts admitted={}, active=None, history=[]. admit(version,record,evidence) requires: record.name starts namespace+'.' with a nonempty suffix; record.status=='active'; record.source_digest==evidence.source_digest; record.tools_digest==evidence.live_digest; both digests are 64 lowercase hex characters; evidence.namespace==namespace. Any missing/invalid check raises ValueError with no mutation. Reject every duplicate version, even with identical data. On success deep-copy record into admitted[version], set active=version, append ('admit',version), return version. version and namespace are provided nonempty strings.
observe(live_digest,status) returns False if no active version. If status is not 'active' or digest mismatches the active pin, append ('quarantine',active), set active=None, return False. Otherwise return True without history mutation.

## Bonus contract

rollback(version) requires a previously admitted version or raises KeyError. Set active=version and append ('rollback',version). Preserve all admitted versions and previous history. No network routing is actually changed.

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
