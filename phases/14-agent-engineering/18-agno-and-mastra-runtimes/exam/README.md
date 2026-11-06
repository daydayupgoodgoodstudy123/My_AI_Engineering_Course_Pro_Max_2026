# AgnoMastra pair session

AgnoMastra is a small agent runtime with two halves. The Agno-shaped half (`agnomastra/agno.py`) is a stateless request handler: every request gets a fresh agent, and the conversation lives in a session store. The Mastra-shaped half (`agnomastra/mastra.py`) has typed tools whose calls are checked against an input schema, an agent that calls them, and workflows. Around them sit composite storage (`storage.py`), a capacity planner (`capacity.py`), a streaming backend (`server.py`) and a schema checker for typed workflows (`schemas.py`). No model or network is involved: the tests supply every model.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_runtime_handlers`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the runtime misbehaves.

## Pt 2 `test_composite_storage`

Store memory, workflow snapshots and observability events, each in its own backend.

## Pt 3 `test_capacity_plan`

Plan capacity for an agent request path, and find out what a faster runtime would buy.

## Pt 4 `test_streaming_backend`

Stream model replies over HTTP/1.1.

## Pt 5 `test_flow_schemas`

Type-check workflows, including nested ones.
