# WebGym pair session

WebGym is a small WebArena-style harness. Agents drive a pinned toy shopping app (`webgym/app.py`) through an `Env` that records every action, and `webgym/harness.py` judges each episode on the app's final state and counts its steps against a gold trajectory. The other modules store pinned app snapshots, measure trajectory efficiency, run episodes in parallel and evaluate nested success conditions.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written. No test calls a model or the network: every agent is a scripted function the tests supply.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_suite_judging`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the suite runner reports the wrong results.

## Pt 2 `test_snapshot_store`

Store pinned app snapshots by content.

## Pt 3 `test_trajectory_efficiency`

Align agent trajectories with gold ones, and report steps over gold.

## Pt 4 `test_parallel_episodes`

Run episodes concurrently and stream one CSV record per episode.

## Pt 5 `test_goal_predicates`

Evaluate nested success conditions, and explain why one failed.
