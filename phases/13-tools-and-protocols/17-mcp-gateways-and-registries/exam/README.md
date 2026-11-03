# mcpgateway pair session

mcpgateway is a small MCP gateway on the stateless `2026-07-28` wire: one endpoint in front of several backend MCP servers. `mcpgateway/gateway.py` takes each request on its own: it authenticates the caller, checks the routing headers against the body, asks the policy, spends the caller's rate limit (`mcpgateway/limits.py`) and sends the backend a fresh request of its own. `mcpgateway/policy.py` makes the runtime allow or deny decision, `mcpgateway/audit.py` keeps the audit trail, `mcpgateway/relay.py` relays a backend's request-scoped stream to the client and remembers where each task lives, and `mcpgateway/chain.py` rebuilds calls from the audit trail. The backends in `mcpgateway/backends.py` are in-process fakes that the tests script; `mcpgateway/wire.py` builds and checks request envelopes.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_forward_call`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why allowed calls don't make it through the gateway.

## Pt 2 `test_audit_log`

Build the audit log.

## Pt 3 `test_runtime_policy`

Decide every call from the live policy, including while the policy service is down.

## Pt 4 `test_sse_relay`

Relay a backend's stream to the client.

## Pt 5 `test_decision_chain`

Rebuild each public call from the audit trail.
