# Review actions before execution

Original interview simulation · 45 minutes · Python 3.10+ · standard library only.
This is independent practice, not an Edison Scientific question or scoring policy.

## Scenario

Activating a skill must not grant authority. Review a structured action against an independent policy before execution.

## Candidate work

Edit only `starter/main.py`. Keep public signatures and supplied helpers intact.
`tests/test_exam.py` and fixtures are provided. You may add your own tests in a new `tests/test_candidate.py`.
Explain your plan briefly, then implement the core before attempting the bonus.

## Core contract

review(action,policy): action has capability, relative path, origin (None or exact string), side_effect(bool), approved(bool). policy has capabilities(set), root(path), origins(set). Check in order: missing capability -> {'verdict':'deny','rule':'capability'}; absolute path OR resolved path outside root (including symlink escape) -> deny/path; non-None origin not exactly in policy origins -> deny/origin; side_effect True and approved False -> {'verdict':'ask','rule':'approval'}; otherwise {'verdict':'allow','rule':'policy'}. Candidate path is relative to root; root exists. Do not execute, read, or create the candidate file. Input values are provided well typed. This is a policy simulation, not process isolation.

## Bonus contract

command_allowed(argv,allowlist) returns True only if tuple(argv) exactly equals an allowlist tuple. Never accept prefix matches, shell strings, or extra flags. argv must be a list/tuple of strings, otherwise False.

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
