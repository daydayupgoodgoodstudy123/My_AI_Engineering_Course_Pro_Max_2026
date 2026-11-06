# PVEGate pair session

PVEGate is a Prompt-Validator-Executor layer for an agent runtime. Every piece of context carries a source tag (`pvegate/content.py`), and a cheap validator checks each tool call the main model wants to make before the executor runs it (`pvegate/gate.py`). Around the gate sit a long-term memory that remembers where each note came from (`pvegate/memory.py`), a provenance check for tool arguments (`pvegate/provenance.py`), a JSON-RPC front end for the model's tool calls (`pvegate/rpc.py`) and a scanner for nested retrieved content (`pvegate/nested.py`). There is no real model or network: the tests supply the tools and the human.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_pve_session`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the gate lets the wrong calls through and blocks the right ones.

## Pt 2 `test_memory_store`

Keep the agent's notes in SQLite, with where each one came from.

## Pt 3 `test_provenance_check`

Find tool arguments that were copied from content the user never wrote.

## Pt 4 `test_rpc_per_call`

Implement `handle_line` to validate each JSON-RPC tool call against the current evidence history, then decide its effect and reply. The async `serve` transport loop is supplied.

## Pt 5 `test_nested_scan`

Look for injected instructions inside nested retrieved content.
