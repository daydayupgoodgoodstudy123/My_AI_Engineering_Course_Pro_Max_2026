# Outcomes pair session

Outcomes separates an observable result from a proposed product. `outcomes/frame.py` checks a frame and its compatibility receipts, `revisions.py` keeps its history, `leaks.py` finds finite lexical solution indicators, `edits.py` renders a workshop's issue changes, and `tree.py` keeps boundaries across sub-outcomes.

The goal is to write application code so every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_outcome_frame`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the frame gate accepts unearned choices.

## Pt 2 `test_revision_history`

Keep a frame's complete revision history.

## Pt 3 `test_lexical_solution_leakage`

Find the supplied lexical indicators without rewriting the evidence.

## Pt 4 `test_workshop_edits`

Show issue changes while people revise the frame.

## Pt 5 `test_outcome_decomposition`

Carry users, constraints and non-goals through a decomposition.
