# tokengate pair session

tokengate is the authorization gate of an MCP server (the resource server) for the stateless 2026-07-28 protocol. Every request carries its own `Authorization: Bearer ...` token and is checked on its own. `tokengate/resource.py` validates JWT access tokens against the issuers in the server's protected-resource metadata (`tokengate/prm.py`), with a JWKS cache that has to survive the authorization server rotating its keys. `tokengate/idp.py` is an in-process stand-in for the authorization servers; its `jwks()` and `introspect()` are the network calls, so leave that file as it is. `tokengate/gate.py` is the front door that decides every request, `tokengate/introspection.py` caches introspection results for opaque tokens, `tokengate/timeline.py` replays incidents, and `tokengate/redirects.py` checks deprecated dynamic client registrations.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_jwks_and_audience`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the validator fails.

## Pt 2 `test_introspection_cache`

Cache introspection results so that every replica can use them, without ever storing a token.

## Pt 3 `test_gate_decisions`

Decide every request: the issuer's configuration picks how a token is checked, and every dependency failure has a declared outcome.

## Pt 4 `test_incident_replay`

Replay an incident timeline and log each decision as CSV, as it happens.

## Pt 5 `test_dcr_redirects`

Check deprecated dynamic client registrations against the redirect URI rules for native and web clients.
