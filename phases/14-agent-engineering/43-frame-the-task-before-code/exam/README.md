# TaskFrame pair session

TaskFrame checks a coding agent's task frame before the agent edits anything. `taskframe/frame.py` validates a frame's goal, boundaries, acceptance evidence and fact receipts against a read-only snapshot of the repository (`taskframe/repo.py`). `taskframe/pins.py` keeps the lines a frame cites, `taskframe/decisions.py` says whether reconnaissance has earned every planned decision, `taskframe/recon.py` reads code-search hits, and `taskframe/narrow.py` turns a broad allowed path into a small one.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_validate_frame`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the validator turns down frames it should accept, and accepts frames it should turn down.

## Pt 2 `test_receipt_pins`

Pin the lines a frame cites, and tell what happened to them in a later commit.

## Pt 3 `test_decision_coverage`

Decide whether the agent may plan the change, must look further, or must ask first.

## Pt 4 `test_recon_stream`

Read search hits only until every decision has a constraint.

## Pt 5 `test_narrow_allowed`

Split a broad allowed path into the smallest safe set.
