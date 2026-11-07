# SplitCase pair session

SplitCase replays fixed single-window and specialist designs. `splitcase/routing.py` prepares a specialist's input, `splitcase/usage.py` records fixture calls, and `splitcase/service.py` wires these records together. Designs live in `splitcase/store.py`; context and summary-boundary reports live in `splitcase/accounting.py`.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_addressed_replay_and_usage`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the replay records fail.

## Pt 2 `test_fixed_design_snapshot`

Persist and reopen the complete local design snapshot, including ordered repeated-recipient messages and their original text.

## Pt 3 `test_loss_aware_fixed_comparison`

Compare the two supplied fixed designs using the declared context and fact-loss contract.

## Pt 4 `test_completed_stage_csv`

Encode one completed stage's domain row. CSV framing, asynchronous publication and source ownership are supplied.

## Pt 5 `test_nested_context_scope_boundaries`

Report the visible and missing facts at the leaves of the supplied context scope tree. An empty scope has no leaf rows.
