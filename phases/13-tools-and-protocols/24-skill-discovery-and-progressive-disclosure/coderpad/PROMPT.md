# Budget progressive disclosure

Original interview simulation · 45 minutes · Python 3.10+ · standard library only.
This is independent practice, not an Edison Scientific question or scoring policy.

## Scenario

A skill catalog should publish compact metadata and load only the selected resource within its package boundary.

## Candidate work

Edit only `starter/main.py`. Keep public signatures and supplied helpers intact.
`tests/test_exam.py` and fixtures are provided. You may add your own tests in a new `tests/test_candidate.py`.
Explain your plan briefly, then implement the core before attempting the bonus.

## Core contract

catalog(candidates,precedence,budget) receives {'name','description','scope'} dicts and a scope list from highest to lowest priority. Exclude unknown scopes. For each name select the candidate from the highest-priority scope; duplicate names within that winning scope raise ValueError. Sort winners by name, then greedily include each whose cost len(name)+len(description) fits remaining budget; skip an oversized entry and continue. Return copied dicts with only name and description, no body or scope. budget is a nonnegative integer. Resolve ALL collisions before budget filtering.
reference(root,relative,max_chars) returns UTF-8 text truncated to max_chars. Reject absolute paths or resolved paths outside root, including symlink escape, with ValueError. Missing files raise FileNotFoundError. root exists; max_chars is a valid nonnegative integer. This is a local loader, not an OS sandbox.

## Bonus contract

activation(entry,body) returns {'name':entry['name'],'instructions':body}, without mutating entry or adding instructions to catalog entries.

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
