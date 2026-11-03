# scopegate pair session

scopegate is a small MCP server for notes, written for the stateless 2026-07-28 protocol. Scope is explicit: every `notes_delete` call names its `workspaceUri`, `scopegate/scope.py` decides whether a note's file URI is inside that workspace, and `scopegate/grants.py` decides who may touch which workspace. A deletion is always confirmed through a form-mode elicitation carried in an `input_required` result (`scopegate/server.py`), and a one-time nonce in the signed `requestState` stops a confirmation from being used twice (`scopegate/replay.py`, `scopegate/notedb.py`). `scopegate/connect.py` and `scopegate/client.py` connect a third-party report service through URL mode.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_scope_and_replay`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the scope code fails.

## Pt 2 `test_replay_db_roundtrip`

Move the replay protection into SQLite, so that several server processes share it.

## Pt 3 `test_delete_confirmation`

Finish `notes_delete`: ask which note to delete, then act on the user's answer.

## Pt 4 `test_url_mode_flow`

Connect the report service out of band, through a URL-mode elicitation.

## Pt 5 `test_nested_grants`

Authorize nested workspaces.
