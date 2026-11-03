# AppBridge pair session

AppBridge is a small MCP Apps stack on the `2026-07-28` wire. `appbridge/server.py` is the lesson's server: `tools/list` binds the `notes_timeline` tool to a `ui://` resource, and `resources/read` serves the App's HTML. Everything else is the host. `appbridge/review.py` reviews a resource before a View runs it, `appbridge/cache.py` keeps App resources on disk, `appbridge/policy.py` decides what a mounted View may do, `appbridge/bridge.py` runs the postMessage bridge to one View, and `appbridge/invalidation.py` works out what a change invalidates. `appbridge/wire.py` builds request envelopes.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_ui_fallback`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why hosts don't get the UI, or the fallback, that they should.

## Pt 2 `test_app_cache_roundtrip`

Build the App resource cache.

## Pt 3 `test_host_policy`

Decide what a mounted View may load, use and do.

## Pt 4 `test_bridge_lifecycle`

Run the bridge between the host and one View.

## Pt 5 `test_invalidation_plan`

Work out which cache entries and Views a change invalidates.
