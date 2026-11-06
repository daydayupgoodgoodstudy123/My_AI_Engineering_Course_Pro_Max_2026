# FlowMap pair session

FlowMap reconstructs the workflow people actually perform. `flowmap/audit.py` checks evidence quality, `store.py` keeps workflow snapshots, `discover.py` finds the four kinds of workflow concern and handoff risk, `recording.py` segments an event recording, and `variants.py` preserves different observed paths.

The goal is to write application code so every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_workflow_evidence`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the audit inflates or understates the evidence.

## Pt 2 `test_workflow_store_roundtrip`

Keep the original workflow and every receipt between sessions.

## Pt 3 `test_four_things_and_handoffs`

Find workflow concerns while keeping unconfirmed leads visible.

## Pt 4 `test_recording_segments`

Turn an arriving recording into observed steps.

## Pt 5 `test_observed_workflow_variants`

Preserve different users' real paths without inventing an average workflow.
