# InitProbe pair session

InitProbe is the init script an agent runs before it starts work. `initprobe/paths.py` pins the repo's paths before any probe looks at them. A probe (`initprobe/probes.py`) checks one thing about the workbench and reports pass, warn or fail. `initprobe/runner.py` runs probes and keeps a `prereqs.lock` so that a later run can skip them. `initprobe/history.py` keeps every run in an append-only log, `initprobe/plan.py` runs the probes in the order their needs allow and decides whether the agent may launch, `initprobe/tap.py` reports a run as TAP while it runs, and `initprobe/lkg.py` holds HEAD to a drift budget against the last-known-good commit. `initprobe/service.py` wires these together for the pre-task hook.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_probe_runner`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why init fails.

## Pt 2 `test_run_history`

Keep a history of init runs.

## Pt 3 `test_probe_plan`

Run the probes in dependency order, and decide whether the agent may launch.

## Pt 4 `test_tap_stream`

Report a run as TAP while it runs.

## Pt 5 `test_lkg_diff`

Diff HEAD against the last-known-good tree.
