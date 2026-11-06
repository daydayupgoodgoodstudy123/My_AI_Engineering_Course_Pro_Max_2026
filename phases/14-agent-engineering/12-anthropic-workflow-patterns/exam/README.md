# Workflows pair session

Workflows is a small support desk built from Anthropic's workflow patterns. `workflows/patterns.py` has prompt chaining, routing, parallel voting and evaluator-optimizer as async functions over an LLM callable. Every run can be kept for auditors as an XML document (`workflows/audit.py`), a code review fans out to the workers an orchestrator picks (`workflows/orchestrator.py`), live tickets are routed as they arrive (`workflows/dispatch.py`), and a workflow spec's cost can be bounded before it runs (`workflows/bounds.py`). The models are scripted stand-ins in the tests; nothing calls a real LLM or the network.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_patterns`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the workflow patterns misbehave.

## Pt 2 `test_audit_record`

Keep each run as an XML document an auditor can read.

## Pt 3 `test_orchestrator`

Let an orchestrator decide which workers run, and combine what they find.

## Pt 4 `test_route_stream`

Route live tickets as they arrive.

## Pt 5 `test_cost_bounds`

Bound what a nested workflow can cost before it runs.
