# ToolCall pair session

ToolCall is a small function-calling runtime with an evaluation harness. `toolcall/registry.py` validates and runs the model's tool calls, `toolcall/cases.py` keeps BFCL-style evaluation cases in a dbm file, `toolcall/scoring.py` grades a model's calls against them, `toolcall/pipeline.py` runs a suite against the model and reports it as TAP, and `toolcall/chains.py` replays multi-turn tool chains. `toolcall/drive.py` is the fake drive API that state-based checks run against, and `toolcall/service.py` wires the CI job together.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_registry_dispatch`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the registry fails.

## Pt 2 `test_case_bank`

Store the evaluation cases.

## Pt 3 `test_bfcl_scoring`

Grade a model's calls the BFCL way.

## Pt 4 `test_suite_tap`

Run a suite against the model, several cases at a time, and report it as TAP.

## Pt 5 `test_call_chains`

Replay tool chains whose arguments point at earlier results.
