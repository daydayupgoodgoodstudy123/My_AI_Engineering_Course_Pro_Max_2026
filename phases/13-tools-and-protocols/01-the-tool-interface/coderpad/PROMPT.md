# A bounded tool runner

Original interview simulation · 45 minutes · Python 3.10+ · standard library only.
This is independent practice, not an Edison Scientific question or scoring policy.

## Scenario

Your team has a scripted model and a tool registry. Finish the execution boundary so malformed model calls never reach a tool.

## Candidate work

Edit only `starter/main.py`. Keep public signatures and supplied helpers intact.
`tests/test_exam.py` and fixtures are provided. You may add your own tests in a new `tests/test_candidate.py`.
Explain your plan briefly, then implement the core before attempting the bonus.

## Core contract

1. execute(registry, name, arguments): registry maps names to {'parameters': [required integer parameter names], 'executor': callable}. Return {'ok': True, 'value': executor(arguments)} on success. Arguments must be a dict with exactly those keys and type(value) is int (bool is rejected). Unknown name returns {'ok': False, 'error': 'unknown_tool'}; invalid arguments returns error 'invalid_arguments'; any Exception raised by the executor becomes error 'execution_error'. Never invoke an executor for rejected arguments.
2. run_loop(registry, decisions, max_calls=3): decisions is a finite list of {'tool': name, 'arguments': dict} or {'final': string}. Return {'results': [execute results], 'stop': 'final'|'limit'|'exhausted', 'answer': string|None}. A call attempt counts even when execute returns an error. Check the call limit BEFORE reading the next decision, including a final decision. No final decision means answer None. Empty decisions stops as exhausted. max_calls must have exact type int and be >0, otherwise raise ValueError. Decision envelope shapes are provided valid.

## Bonus contract

describe(registry) returns tool names sorted lexicographically, without invoking executors.

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
