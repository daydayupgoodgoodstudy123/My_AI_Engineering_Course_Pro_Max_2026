# Validate a portable skill bundle

Original interview simulation · 45 minutes · Python 3.10+ · standard library only.
This is independent practice, not an Edison Scientific question or scoring policy.

## Scenario

A catalog should reject malformed skill metadata before activation. Implement a deliberately small portable-frontmatter subset.

## Candidate work

Edit only `starter/main.py`. Keep public signatures and supplied helpers intact.
`tests/test_exam.py` and fixtures are provided. You may add your own tests in a new `tests/test_candidate.py`.
Explain your plan briefly, then implement the core before attempting the bonus.

## Core contract

parse(text) requires first line '---', then exactly two unique single-line key:value entries named name and description in either order, then a closing '---' line, then nonempty body after trimming. Strip leading/trailing whitespace around keys/values. No YAML quoting, multiline values, comments, or additional keys are supported in this exercise. name must match [a-z][a-z0-9]*(?:-[a-z0-9]+)* and be <=64 characters; description trimmed length 1..1024. Return {'name','description','body'} with stripped values and body; any violation raises ValueError.
validate_bundle(directory_name,text) calls parse and additionally requires name==directory_name; return parsed metadata or raise ValueError. Runtime permissions and invocation flags do not belong to this exercise's portable subset.

## Bonus contract

classify(need) maps 'reusable workflow' -> 'skill', 'external action' -> 'tool', 'always-on repository rules' -> 'instructions', 'event callback' -> 'hook'; unknown needs return 'ordinary code'. Exact strings, no fuzzy routing.

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
