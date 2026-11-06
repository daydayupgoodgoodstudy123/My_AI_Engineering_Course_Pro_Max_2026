# SemConv pair session

SemConv records OpenTelemetry GenAI spans for an in-process agent. `semconv/tracer.py` keeps the spans of one trace and captures content by reference, `semconv/agent.py` builds a small ReAct agent (`create_agent`) and runs it (`run_agent`), emitting `create_agent`, `invoke_agent`, `chat` and `tool_call` spans (the model and the tools are plain async functions the caller supplies), and the other modules read those spans back for storage, dashboards and live export.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_agent_spans`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why an agent's spans come out wrong.

## Pt 2 `test_content_store_roundtrip`

Keep captured content in SQLite, so spans carry only row ids.

## Pt 3 `test_tool_errors_by_model`

Find out which tool errors go with which models, from the span attributes alone.

## Pt 4 `test_span_feed`

Stream the spans of a run as they end.

## Pt 5 `test_agent_usage_rollup`

Roll token usage up through agents that call agents.
