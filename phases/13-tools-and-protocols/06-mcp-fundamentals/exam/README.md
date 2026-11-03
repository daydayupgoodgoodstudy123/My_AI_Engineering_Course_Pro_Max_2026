# MCPCore pair session

MCPCore is the core of a small MCP notes server, written for MCP `2026-07-28` without a framework. `mcpcore/wire.py` builds and validates JSON-RPC messages and `mcpcore/server.py` answers them. `mcpcore/transcript.py` keeps a SQLite transcript of what crossed the wire, `mcpcore/lifecycle.py` checks each incoming message before any handler runs, `mcpcore/tracer.py` labels a live message stream, and `mcpcore/capabilities.py` matches nested client capabilities.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_stateless_requests`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why requests are not handled on their own.

## Pt 2 `test_transcript_roundtrip`

Build the transcript store.

## Pt 3 `test_request_lifecycle`

Check each incoming message, in the right order.

## Pt 4 `test_trace_stream`

Label a live message stream, one line per message.

## Pt 5 `test_required_capabilities`

Report which client capabilities a request is missing.
