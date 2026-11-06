# RuleCheck pair session

RuleCheck turns a repo's agent instructions into rules a workbench can check. Rules live in `docs/agent-rules.md`, one per `## ` heading, each with a category, a check and a severity; `rulecheck/rules.py` reads that file. `rulecheck/checker.py` is the lesson's checker: one method per check, scored against a summary of one agent turn (`rulecheck/turn.py`). Around it sit a writer for the rule file (`rulecheck/rulefile.py`), a judge that reads a turn's events in order (`rulecheck/timeline.py`), a runtime that enforces the rules while a turn runs (`rulecheck/runtime.py`) and an audit of the `AGENTS.md` router (`rulecheck/router.py`). Nothing calls a model: turns are lists of events that the tests write.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_rule_report`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the rule report is wrong.

## Pt 2 `test_rule_file`

Write the rule file back out, so that every change to it reads well in a diff.

## Pt 3 `test_turn_judgement`

Judge a turn from its events, in order, the way each category of rule reads them.

## Pt 4 `test_runtime_tap`

Enforce the rules while the turn runs, and report each rule as TAP.

## Pt 5 `test_router_reachability`

Check that an agent can get from `AGENTS.md` to every rule in two links.
