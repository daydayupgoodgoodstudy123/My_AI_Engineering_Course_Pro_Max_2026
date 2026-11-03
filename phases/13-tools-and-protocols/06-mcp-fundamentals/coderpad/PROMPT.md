# Validate an independent RPC request

Original interview simulation · 45 minutes · Python 3.10+ · standard library only.
This is independent practice, not an Edison Scientific question or scoring policy.

## Scenario

Implement a tiny stateless RPC dispatcher. The exercise pins a local course fixture revision; it does not implement the entire MCP specification.

## Candidate work

Edit only `starter/main.py`. Keep public signatures and supplied helpers intact.
`tests/test_exam.py` and fixtures are provided. You may add your own tests in a new `tests/test_candidate.py`.
Explain your plan briefly, then implement the core before attempting the bonus.

## Core contract

VERSION is provided. dispatch(message) accepts only dicts with jsonrpc='2.0', id of exact type int or nonempty str, method a nonempty str, params a dict, and params._meta a dict containing protocolVersion (str) and clientCapabilities (dict). Extra fields are allowed. Invalid envelope returns {'jsonrpc':'2.0','id':None,'error':{'code':-32600}}. Valid envelope with unsupported version returns error -32022, echoing id. Unknown method returns -32601. server/discover returns result {'resultType':'complete','name':'interview-server'}. tools/list returns result {'resultType':'complete','tools':[]}. Error checks run in this order: envelope, version, method. No initialization or remembered connection state.

## Bonus contract

request(request_id, method, params=None) returns a valid request with VERSION and empty clientCapabilities. Deep-copy params and overwrite its _meta with this exercise's metadata. Do not mutate caller input.

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
