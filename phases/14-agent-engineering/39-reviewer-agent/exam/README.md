# Reviewer pair session

Reviewer is a small reviewer-agent service for an agent workbench. When the builder agent closes a task, the reviewer reads what it left behind (the diff summary, the state, the runtime feedback and the verification gate's verdict) and scores it on a five-dimension rubric (`reviewer/rubric.py`). Reports are kept as an append-only history on disk (`reviewer/reports.py`), two reviewers' evidence-backed drafts are reconciled into one report (`reviewer/reconcile.py`), builder and reviewer turns alternate until the work passes (`reviewer/rounds.py`), and the review's comment threads are tracked until the reviewer resolves them (`reviewer/threads.py`). In production every scorer is a model call; here the scorers are deterministic and the tests script the builder and the reviewers, so nothing calls a model or the network.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_rubric_review`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the reviews come out wrong.

## Pt 2 `test_report_history`

Keep every review report on disk.

## Pt 3 `test_reconcile_reviewers`

Reconcile two reviewers who back their scores with evidence.

## Pt 4 `test_build_review_rounds`

Let builder and reviewer take turns, and stream each round as it ends.

## Pt 5 `test_comment_threads`

Work out which review threads are still open.
