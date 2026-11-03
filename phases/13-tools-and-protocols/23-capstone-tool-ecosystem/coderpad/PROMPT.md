# Orchestrate a bounded tool job

Original interview simulation · 45 minutes · Python 3.10+ · standard library only.
This is independent practice, not an Edison Scientific question or scoring policy.

## Scenario

Finish a coordinator over a supplied fake tool client. Keep authorization, discovery, execution, and task polling observable.

## Candidate work

Edit only `starter/main.py`. Keep public signatures and supplied helpers intact.
`tests/test_exam.py` and fixtures are provided. You may add your own tests in a new `tests/test_candidate.py`.
Explain your plan briefly, then implement the core before attempting the bonus.

## Core contract

run(client,tool,args,allowed,max_polls=3): validate max_polls has exact type int and is >=0, else ValueError. If tool not in allowed, raise PermissionError BEFORE calling client. Then call client.discover() once (returns list of tool names), and raise KeyError if tool absent. Call client.call(tool,args) once. Responses are either {'status':'completed','value':any}, {'status':'failed'}, or {'status':'working','task_id':str}. For working, call client.poll(task_id) at most max_polls times, stopping at completed/failed. Working poll results retain the same task_id. Return {'status':'completed'|'failed'|'timeout','value':value only for completed else None,'trace':['discover','call', followed by one 'poll' per poll]}. Underlying exceptions propagate. No automatic mutation retry or real MCP/A2A/OAuth integration.

## Bonus contract

evidence(report) returns {'completed':report.status=='completed','polls':count of 'poll' in trace,'live_integration':False}; do not infer a real deployment from this simulation.

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
