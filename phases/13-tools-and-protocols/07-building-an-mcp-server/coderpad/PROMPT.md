# Finish a notes tool server

Original interview simulation · 45 minutes · Python 3.10+ · standard library only.
This is independent practice, not an Edison Scientific question or scoring policy.

## Scenario

The RPC transport exists. Finish the in-memory application service used by the notes tools.

## Candidate work

Edit only `starter/main.py`. Keep public signatures and supplied helpers intact.
`tests/test_exam.py` and fixtures are provided. You may add your own tests in a new `tests/test_candidate.py`.
Explain your plan briefly, then implement the core before attempting the bonus.

## Core contract

NotesServer starts with no notes and next_id=1. call(name, args): notes_create requires exactly {'title': str}, trimmed length 1..80; on success allocate consecutive integer id and return {'ok':True,'value':{'id':id,'title':trimmed}}. notes_get requires exactly {'id': exact int}; missing id returns {'ok':False,'error':'not_found'}. Invalid args return error 'invalid_arguments'; unknown tool returns error 'unknown_tool' before checking args. Rejected creates must not consume ids or change data. Returned note dicts are copies, so callers cannot mutate internal state. Repeated gets are read-only.

## Bonus contract

list_tools() returns ['notes_create','notes_get']; search(query) returns copied matching notes sorted by id, using case-insensitive substring search in titles. Empty query matches all notes.

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
