# Delegate pair session

Delegate validates isolated work units, stores each worker's evidence separately, and checks material handoffs before planning an integration. `delegate/plan.py` owns write claims; `integrate.py` owns merge decisions.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_isolated_ownership_plan`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the ownership report is wrong.

## Pt 2 `test_evidence_isolation_roundtrip`

Keep each work unit's evidence separate and immutable.

## Pt 3 `test_material_handoff_integration`

Read material handoffs and plan a verified integration.

## Pt 4 `test_online_handoff_verdicts`

Emit integration verdicts as worker receipts arrive.

## Pt 5 `test_nested_ownership_and_parallelism`

Audit nested write ownership against dependency order.
