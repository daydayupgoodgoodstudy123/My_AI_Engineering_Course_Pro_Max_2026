# notesrv pair session

notesrv is a small MCP server for notes. It speaks the stateless 2026-07-28 protocol: every request carries its own metadata, which `notesrv/protocol.py` checks, and `notesrv/server.py` routes the methods (discovery, tools, resources, prompts). Notes live in a store: `notesrv/notes.py` keeps them in memory and `notesrv/notedir.py` on disk. Tools are in `notesrv/tools.py`, `notesrv/stdio.py` runs the server over stdin and stdout, and `notesrv/dualera.py` lets older 2025-11-25 clients in.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_dispatch_contract`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the server fails.

## Pt 2 `test_note_dir_roundtrip`

Keep notes on disk, so they survive a restart.

## Pt 3 `test_tool_call_errors`

Finish `tools/call`, including a `notes_delete` tool.

## Pt 4 `test_stdio_loop`

Serve the server over stdio.

## Pt 5 `test_dual_era_connections`

Let 2025-11-25 clients connect without making the modern core stateful.
