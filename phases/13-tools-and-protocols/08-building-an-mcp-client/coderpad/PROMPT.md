# Merge and route remote tools

Original interview simulation · 45 minutes · Python 3.10+ · standard library only.
This is independent practice, not an Edison Scientific question or scoring policy.

## Scenario

A client connects to several fake peers. Merge discovered tools and route calls without silent overwrites.

## Candidate work

Edit only `starter/main.py`. Keep public signatures and supplied helpers intact.
`tests/test_exam.py` and fixtures are provided. You may add your own tests in a new `tests/test_candidate.py`.
Explain your plan briefly, then implement the core before attempting the bonus.

## Core contract

Client(peers) receives a dict peer_name -> object exposing list_tools() and call(tool,args). discover() asks each peer once, validates every tool descriptor has a nonempty string name, and builds public names peer_name+'::'+tool_name. Peer and tool names must not contain '::'. Duplicate local tool names within one peer raise ValueError. Publish the new catalog only after ALL peers succeed; failures preserve the previous catalog. Return sorted public names. Initial catalog is empty. call(public_name,args) routes only a previously discovered name to its owning peer using the unprefixed local name, returns the peer's result, and propagates peer exceptions. Unknown public name raises KeyError. The peers dict itself is provided valid except names may contain the forbidden delimiter.

## Bonus contract

descriptor(public_name) returns a deep copy of the original descriptor with name replaced by public_name. Unknown public name raises KeyError.

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
