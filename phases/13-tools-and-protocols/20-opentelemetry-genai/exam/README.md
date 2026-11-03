# GenAITrace pair session

GenAITrace traces a small tool-calling agent the way the OpenTelemetry GenAI conventions describe it. `genaitrace/tracer.py` starts and ends spans, `genaitrace/agent.py` runs the agent (a chat, three weather lookups through an MCP server, another chat) against scripted stand-ins, and `genaitrace/traces.py` links finished spans back into traces. The rest of the package turns spans into OTLP/JSON (`otlp.py`), keeps them in a log (`spanlog.py`), checks them against the conventions and aggregates the GenAI metrics (`semconv.py`, `metrics.py`), carries the trace across MCP and ships it to a collector (`propagate.py`, `export.py`), and finds where a slow run spent its time (`waterfall.py`).

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_agent_trace`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the agent's trace comes out wrong.

## Pt 2 `test_span_log_roundtrip`

Keep finished spans in a log, exactly.

## Pt 3 `test_conventions_and_metrics`

Hold spans to the GenAI conventions, and aggregate the GenAI metrics.

## Pt 4 `test_propagation_and_export`

Carry the trace into the MCP server, and ship spans in batches.

## Pt 5 `test_where_the_time_went`

Find where a slow run spent its time.
