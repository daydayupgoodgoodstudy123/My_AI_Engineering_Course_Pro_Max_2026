# streamhttp pair session

streamhttp is a small MCP endpoint for the stateless 2026-07-28 Streamable HTTP transport, plus the client side of it. `streamhttp/wire.py` reads a POST: header lookup, the body, and the mirrored routing headers. Drafts live in one SQLite file that every replica opens (`streamhttp/drafts.py`). `streamhttp/server.py` turns one HTTP request into one HTTP response, `streamhttp/sse.py` streams a long tool call, and `streamhttp/client.py` reads a response on the client side.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_read_post`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the request reader fails. Each routing header supplies one exact value for the body.

## Pt 2 `test_shared_drafts`

Keep drafts where every replica can find them.

## Pt 3 `test_http_responses`

Answer every HTTP request the way the 2026-07-28 transport defines.

## Pt 4 `test_request_scoped_sse`

Stream a long tool call.

## Pt 5 `test_layered_decoding`

Read a response on the client side, one layer at a time.
