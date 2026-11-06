# EvalGate pair session

EvalGate is a small eval harness for an agent product. Eval cases live next to the agent code and run through an evaluator-optimizer loop (`evalgate/harness.py`); production sessions can be replayed as cases (`evalgate/replay.py`). Every commit's results are stored as a JSON snapshot (`evalgate/store.py`), and pull requests are gated against main's last-known-good (`evalgate/gate.py`). `evalgate/pipeline.py` wires these together for the CI job.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_harness`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and trace the one-round decisions, refinement feedback and per-case flaky windows.

## Pt 2 `test_snapshot_store`

Store each commit's results.

## Pt 3 `test_merge_gate`

Gate a pull request against main.

## Pt 4 `test_workflow_log`

Report the run in the GitHub Actions log while the cases finish.

## Pt 5 `test_coverage_map`

Check that every guardrail and learned rule is backed by a passing case.
