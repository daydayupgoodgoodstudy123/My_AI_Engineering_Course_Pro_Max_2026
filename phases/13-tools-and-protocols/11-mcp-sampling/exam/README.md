# mrtrkit pair session

mrtrkit is a small MCP 2026-07-28 service whose `summarize_repo` tool needs the client's model. The server (`mrtrkit/server.py`) runs the tool as Multi Round-Trip Requests: it answers `input_required` with an embedded `sampling/createMessage` request and a signed `requestState`, and the client retries the call with the model's answer. `mrtrkit/statetoken.py` is the next requestState format. `mrtrkit/host.py` and `mrtrkit/approvals.py` are the host side, which fulfils those requests with its own model. `mrtrkit/flow.py` describes multi-round flows as a graph of phases. `mrtrkit/protocol.py` holds the wire pieces they share.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_mrtr_rounds`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the second round fails.

## Pt 2 `test_state_token_roundtrip`

Build the version 1 requestState token.

## Pt 3 `test_host_driver`

Drive an MRTR interaction from the host's side.

## Pt 4 `test_concurrent_approvals`

Run many interactions at once, with approvals from the user and a budget per principal.

## Pt 5 `test_phase_graph`

Run multi-round flows from a graph of phases.
