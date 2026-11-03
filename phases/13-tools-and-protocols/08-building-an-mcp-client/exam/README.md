# multipeer pair session

multipeer is the client side of an agent host that talks to several MCP servers. `multipeer/client.py` keeps a record for each peer and routes tool calls to the peer that owns each tool. `multipeer/pending.py` matches answers to the requests in flight, and `multipeer/protocol.py` holds the wire helpers for the modern 2026-07-28 protocol and the legacy 2025-11-25 one. Pinned peers are configured in an INI file (`multipeer/peerconf.py`). Each stdio peer's protocol era is negotiated by `multipeer/negotiate.py`. `multipeer/pool.py` runs stdio peers as processes, and `multipeer/namespace.py` merges every peer's tools into one namespace.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_route_calls`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why calls go wrong.

## Pt 2 `test_peer_config_roundtrip`

Load and save the pinned peer configuration.

## Pt 3 `test_era_negotiation`

Decide which protocol era a stdio peer speaks, and fail closed when the evidence is not there.

## Pt 4 `test_stdio_pool`

Run calls to several stdio peers at once, and survive a peer that crashes.

## Pt 5 `test_namespace_merge`

Merge every peer's tools into one namespace.
