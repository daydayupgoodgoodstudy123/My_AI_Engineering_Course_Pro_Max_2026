# FeedLog pair session

FeedLog is a small feedback runner for coding agents. Every shell command the agent runs goes through `feedlog/runner.py`, which runs it, redacts secrets in its output (`feedlog/redact.py`), cuts long output down to its first and last lines (`feedlog/truncate.py`) and writes one structured record (`feedlog/record.py`) for the agent's next turn to read. Records go to a JSONL log that rotates by size (`feedlog/store.py`), a long-running command can be followed while it runs (`feedlog/live.py`), and retries are linked into chains for review (`feedlog/chains.py`). The tests drive scripted fake commands and processes, apart from two tiny `python -c` runs.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_runner`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the runner fails.

## Pt 2 `test_rotating_log`

Keep the records in a JSONL log that rotates by size, so the agent's loop reads one small file and CI still gets the whole history.

## Pt 3 `test_truncate_lines`

Cut long output down deterministically: the first lines, the last lines, and a marker in between.

## Pt 4 `test_follow`

Follow a command while it runs: relay its output line by line, in bounded memory, and stop at the deadline.

## Pt 5 `test_retry_chains`

Link retries into chains, so a review sees every failed attempt before the final result.
