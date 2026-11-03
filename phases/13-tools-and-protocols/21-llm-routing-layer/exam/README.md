# ModelRouter pair session

ModelRouter is a small LLM routing gateway. Clients send OpenAI-shaped chat requests to an alias such as `smart`, and `modelrouter/gateway.py` redacts PII (`modelrouter/guard.py`), tries the alias's fallback chain, prices the call (`modelrouter/pricing.py`) and enforces each team's monthly budget (`modelrouter/budget.py`). Every call goes into a SQLite cost ledger (`modelrouter/ledger.py`). `modelrouter/balancer.py` spreads an alias over weighted deployments and keeps EU users in EU regions, `modelrouter/latency.py` sends live traffic to whichever model has been fastest lately, and `modelrouter/aliases.py` expands aliases that point at other aliases. Nothing goes over the network: the tests stand in for the providers with scripted fakes.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_route_and_charge`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why routing a support conversation fails.

## Pt 2 `test_cost_ledger`

Build the cost ledger.

## Pt 3 `test_weighted_pools`

Spread an alias over its deployments, keep EU traffic in the EU, and stop retrying when the budget runs out.

## Pt 4 `test_latency_routing`

Route live traffic to the fastest healthy model, and log each decision as it is made.

## Pt 5 `test_alias_expansion`

Expand aliases that refer to other aliases.
