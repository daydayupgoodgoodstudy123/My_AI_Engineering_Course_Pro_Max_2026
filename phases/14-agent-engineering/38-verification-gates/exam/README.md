# VerifyGate pair session

VerifyGate is the verification gate of an agent workbench: it decides whether a task is actually done from what the task left behind, never from what the agent says. `verifygate/checks.py` turns each artifact into findings: the feedback records of the commands the agent ran, the scope report, the rule report and the coverage report. A human can sign off on a block finding with a signed override (`verifygate/signing.py`), which `verifygate/gate.py` applies. Around these sit the override log (`verifygate/overridelog.py`), the verdict and the one report file CI reads (`verifygate/gate.py`, `verifygate/report.py`), a Markdown summary for PR comments (`verifygate/summary.py`) and gating for a stack of commits (`verifygate/stack.py`). Nothing calls an LLM or the network.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_acceptance_and_overrides`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the acceptance check and the overrides fail.

## Pt 2 `test_override_log`

Keep the signed overrides in a file that only ever grows.

## Pt 3 `test_verdict_and_report`

Turn the four artifacts into one verdict, and write it where CI reads it.

## Pt 4 `test_summary_stream`

Keep a Markdown summary up to date while the agent's commands finish.

## Pt 5 `test_pr_stack`

Gate a stack of commits, each against the one it sits on.
