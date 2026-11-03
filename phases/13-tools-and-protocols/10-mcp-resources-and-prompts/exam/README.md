# uricatalog pair session

uricatalog is a small MCP server for a notes catalog, plus the host code that talks to it. It speaks the stateless 2026-07-28 protocol. `uricatalog/server.py` answers one request at a time for the caller the transport authenticated: notes are resources at `notes://` URIs, `review_note` is a prompt, and `subscriptions/listen` opens a stream that `uricatalog/subscriptions.py` keeps. On the host side, `uricatalog/cache.py` keeps results on disk under their cache hints, and `uricatalog/client.py` runs several subscriptions over one channel. `uricatalog/templates.py` routes resource-template URIs.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_reads_prompts_and_subscriptions`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the server fails.

## Pt 2 `test_response_cache_roundtrip`

Cache results on the host, as their cache hints allow, so that they survive a restart.

## Pt 3 `test_resources_list_pages`

Page through resources/list.

## Pt 4 `test_shared_channel`

Run three subscriptions and an ordinary request over one shared channel.

## Pt 5 `test_template_routes`

Route URIs through resource templates.
