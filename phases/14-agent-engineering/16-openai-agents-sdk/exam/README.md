# Handoffs pair session

Handoffs is a small agent runtime in the shape of the OpenAI Agents SDK. An agent (`handoffs/agents.py`) has instructions, tools, guardrails and handoffs, and each handoff reaches the model as a tool named `transfer_to_<agent>`. `handoffs/runner.py` runs one user message through the agents, checks the guardrails (`handoffs/guardrails.py`) and records a span for every step (`handoffs/tracing.py`). Each agent's model is a plain Python function that the tests supply, so everything runs offline. Around the runner sit a session store (`handoffs/session.py`), history nesting for handoffs (`handoffs/nesting.py`), trace processors (`handoffs/processors.py`) and a check of how the agents connect (`handoffs/graph.py`).

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_runner`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the runner fails.

## Pt 2 `test_session_store`

Keep conversations in SQLite, so that the next run picks up where the last one stopped.

## Pt 3 `test_nested_handoff_history`

Let a handoff pass on a summary of the earlier conversation instead of all of it.

## Pt 4 `test_trace_processors`

Send spans to our own backends as they end, without slowing runs down.

## Pt 5 `test_handoff_graph`

Work out which agents a run can reach, and where the guardrails don't reach.
