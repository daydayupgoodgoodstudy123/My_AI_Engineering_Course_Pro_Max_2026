# RunShape pair session

RunShape runs one agent (`runshape/agent.py`) behind several production runtime shapes. Background jobs go through an in-process queue with async workers, retries and a dead-letter queue (`runshape/queue.py`; `runshape/chaos.py` injects failures), and event-driven agents subscribe on an event bus (`runshape/events.py`). Durable jobs, cron schedules, streaming and event cascades still have to be written.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_queue_and_bus`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the job queue misbehaves.

## Pt 2 `test_job_store`

Keep background jobs in SQLite, so that a crash or a restart loses nothing.

## Pt 3 `test_cron_schedule`

Work out when a cron schedule fires, and what to run after downtime.

## Pt 4 `test_run_stream`

Stream a run to a slow client as server-sent events.

## Pt 5 `test_event_cascade`

Follow an event through everything it triggers.
