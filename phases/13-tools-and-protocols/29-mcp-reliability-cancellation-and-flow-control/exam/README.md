# reliablerpc pair session

reliablerpc is the reliability layer of a small MCP server and its client (MCP `2026-07-28`). `reliablerpc/coordinator.py` tracks in-flight requests and settles the race between completion and cancellation, writing what each request sends into the bounded queues of `reliablerpc/buffer.py`. `reliablerpc/ledger.py` is an idempotency ledger in one SQLite file that every replica opens, `reliablerpc/policy.py` decides what a client may retry and how it cancels on each transport, `reliablerpc/stream.py` answers a long tool call as an SSE stream, and `reliablerpc/race.py` models the whole cancellation race between client, server and wire.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_cancellation_races`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why request completion, progress reporting and bounded buffering misbehave.

## Pt 2 `test_idempotency_ledger`

Run each idempotency key once, whatever the JSON-RPC ids, crashes and replicas.

## Pt 3 `test_retry_and_cancel_signals`

Decide what a client may retry, and how it cancels a call on each transport.

## Pt 4 `test_two_clock_stream`

Stream a long tool call under an idle clock and a maximum clock.

## Pt 5 `test_race_explorer`

Check every interleaving of the cancellation race, not just the two everyone draws.
