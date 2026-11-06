# Harness pair session

Harness is a small agent harness in the shape of the Claude Agent SDK. `harness/core.py` runs an agent's tool calls through `PreToolUse` and `PostToolUse` hooks, records every turn in a session store (`harness/store.py`) and spawns subagents that keep their own context. Tool calls are scripted by the caller instead of chosen by a model, and the subagents in the tests are plain async functions, so everything runs offline. Around the harness sit a session mirror on disk (`harness/mirror.py`), a planner that batches tasks into subagents (`harness/batching.py`), parallel subagents (`harness/fanout.py`) and the subagent tree (`harness/tree.py`).

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_harness_dispatch`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the harness fails.

## Pt 2 `test_session_mirror`

Mirror every session to a JSONL file as it streams, so the next process can load it back.

## Pt 3 `test_batch_plan`

Before spawning anything, plan the batches: what each plan leaves in the orchestrator's context, what it costs in total, and which plan to run.

## Pt 4 `test_parallel_subagents`

Run twenty subagents five at a time, and stream their results back as they finish.

## Pt 5 `test_subagent_tree`

Show the subagent tree, and clean up the sessions that went idle.
