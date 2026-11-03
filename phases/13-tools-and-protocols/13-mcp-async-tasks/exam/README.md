# DurableTask pair session

DurableTask is a small MCP server for the Tasks extension (`io.modelcontextprotocol/tasks`, MCP `2026-07-28`). `tools/call` turns a slow tool into a durable task and returns its handle, and clients poll with `tasks/get`, answer input requests with `tasks/update` and ask for cancellation with `tasks/cancel` (`durabletask/service.py`). Tasks live in a store that every instance shares (`durabletask/store.py`), a worker on each instance moves them through their states, `durabletask/listen.py` pushes task snapshots over SSE for `subscriptions/listen`, and `durabletask/lease.py` keeps two instances' workers off the same task.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_poll_and_cancel`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why polling and cancelling misbehave.

## Pt 2 `test_task_files`

Store tasks in a directory that every instance shares.

## Pt 3 `test_worker_and_input`

Run the worker, and take the client's input by key.

## Pt 4 `test_listen_stream`

Stream task snapshots to a subscriber as they change.

## Pt 5 `test_leases_and_cleanup`

Keep two instances' workers apart, and clean up expired tasks.
