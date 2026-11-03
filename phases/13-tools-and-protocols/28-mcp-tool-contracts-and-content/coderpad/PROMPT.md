# Validate tool result content

Original interview simulation · 45 minutes · Python 3.10+ · standard library only.
This is independent practice, not an Edison Scientific question or scoring policy.

## Scenario

A client rejected valid array outputs and accepted malformed image blocks. Repair its fixed result-contract validator.

## Candidate work

Edit only `starter/main.py`. Keep public signatures and supplied helpers intact.
`tests/test_exam.py` and fixtures are provided. You may add your own tests in a new `tests/test_candidate.py`.
Explain your plan briefly, then implement the core before attempting the bonus.

## Core contract

validate(result,expected_type) returns True or raises ValueError. result must be a dict with content a list. Each block must be a dict: text blocks require type='text', text a string; image blocks require type='image', mimeType='image/png' or 'image/jpeg', and data a nonempty valid standard base64 string. Other block types fail. Extra block fields are allowed. If isError is present it must be exact bool. When isError is True, structured validation is skipped. Otherwise structured is required and must match expected_type: object=dict, array=list, string=str, integer=exact int, number=exact int/float excluding bool, boolean=exact bool, null=None. Unknown expected_type always raises ValueError. This is a fixed top-level type check, not complete JSON Schema validation.

## Bonus contract

pages(fetch) starts with cursor=None, calls fetch(cursor) -> {'items':list,'next':str|None}, concatenates items in page order, and stops on None. Cursors are opaque. A repeated next cursor raises ValueError before fetching it again. Empty-string cursor is valid. First fetch always happens.

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
