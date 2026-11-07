# LeadSynth pair session

LeadSynth receives scoped worker summaries, stores content objects and reconciles typed claims. `leadsynth/workers.py` produces narrow artifacts; `artifacts.py` persists assignments and `synthesis.py` surfaces disagreement.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest. Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_completed_worker_receipts`

Comment out `@pytest.mark.skip('Part 1')`, run pytest, and repair completed worker receipts and runtime diagnostics.

## Pt 2 `test_content_addressed_assignments`

Persist content-addressed summaries and independent query assignment snapshots, then reopen or replace them exactly.

## Pt 3 `test_scoped_conflict_synthesis`

Reconcile scoped typed claims in first-seen provenance order and produce bounded followups while retaining disagreement.

## Pt 4 `test_worker_markdown_blocks`

Project each worker outcome, including an empty completed summary, and the final lead sections into the supplied Markdown driver.

## Pt 5 `test_broad_then_narrow_dossier`

Audit a broad-then-narrow task tree for scope, branch budgets and original ordered leaf attribution.

Local verification boundary: the complete sealed-completion receipt batch is measured, including all output guards. It does not execute real workers or establish research quality or production speedups.
