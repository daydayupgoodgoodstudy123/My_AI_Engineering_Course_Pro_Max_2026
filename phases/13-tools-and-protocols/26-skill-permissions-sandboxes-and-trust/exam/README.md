# SandboxPol pair session

SandboxPol is the permission layer a skill host puts between a skill and the machine. A skill can only suggest an action; the host decides. `sandboxpol/policy.py` is the lesson's reviewer: it classifies one proposed action as allow, require-approval or deny without executing anything, and `sandboxpol/gate.py` hands the actions it allows to the runner. Installed skill packages are kept content-addressed (`sandboxpol/store.py`), a structured request becomes the exact launch the executor may make (`sandboxpol/launch.py`), a sandboxed process's output is relayed back to the host while it runs (`sandboxpol/relay.py`), and an archive's member list is checked before anything is extracted (`sandboxpol/archive.py`).

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_review_gate`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the reviewer lets the wrong actions through.

## Pt 2 `test_install_store`

Keep installed packages, and show what an upgrade would change before it does.

## Pt 3 `test_launch_plan`

Turn a structured request into the launch the executor may make.

## Pt 4 `test_output_relay`

Relay a sandboxed process's output while it runs.

## Pt 5 `test_archive_check`

Check an archive before anything is extracted.
