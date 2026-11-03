# Lint a tool catalog

Original interview simulation · 45 minutes · Python 3.10+ · standard library only.
This is independent practice, not an Edison Scientific question or scoring policy.

## Scenario

Tool authors keep publishing ambiguous descriptors. Build a small deterministic linter for the catalog admission step.

## Candidate work

Edit only `starter/main.py`. Keep public signatures and supplied helpers intact.
`tests/test_exam.py` and fixtures are provided. You may add your own tests in a new `tests/test_candidate.py`.
Explain your plan briefly, then implement the core before attempting the bonus.

## Core contract

lint(tool) returns sorted unique error codes. 'name' if name is not a string matching [a-z][a-z0-9_]{0,39}; 'description' unless description is a string of 1..1024 characters containing both exact substrings 'Use when' and 'Do not use'; 'schema' unless input_schema is a dict with type='object', properties a dict, required a list of unique strings all present in properties, and additionalProperties is False. Missing fields fail their respective checks. Do not validate nested schemas. Never mutate tool.
lint_registry(tools) returns {'findings':[{'index':i,'codes':lint(tool)} for invalid tools], 'duplicates':sorted duplicate string names}. A duplicated name appears once in duplicates even if repeated three times. Invalid non-string names are not duplicate candidates.

## Bonus contract

clean_names(tools) returns sorted unique names of individually valid tools; exclude every name appearing more than once in the input, including duplicates of otherwise invalid entries.

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
