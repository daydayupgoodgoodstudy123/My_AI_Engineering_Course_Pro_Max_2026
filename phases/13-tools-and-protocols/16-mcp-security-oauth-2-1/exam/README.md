# oauthflow pair session

oauthflow is the OAuth side of an MCP host for the 2026-07-28 authorization profile. `oauthflow/discovery.py` finds a resource's authorization server through protected-resource metadata, and `oauthflow/client.py` runs the authorization code flow with PKCE (`oauthflow/pkce.py`) and calls tools with tokens bound to `(issuer, resource)`. Credentials live in a JSON vault (`oauthflow/vault.py`). `oauthflow/stepup.py` and `oauthflow/register.py` decide what to ask for when a server wants more scope, and how the client identifies itself to each issuer. `oauthflow/loopback.py` finishes flows from the browser redirects a native app receives, and `oauthflow/fetch.py` fetches metadata documents from URLs that someone else chose.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_discovery_and_code_flow`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why logging in to the notes server fails.

## Pt 2 `test_vault_snapshot`

Keep the client's credentials in a file, bound to the issuer that minted them.

## Pt 3 `test_step_up_and_enrollment`

Ask for more scope when a server says so, and pick how to enroll with each authorization server.

## Pt 4 `test_loopback_redirects`

Finish authorization flows as the browser redirects come back.

## Pt 5 `test_guarded_fetch`

Fetch metadata documents without being pointed at the inside of the network.
