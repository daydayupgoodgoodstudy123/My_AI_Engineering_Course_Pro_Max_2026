# EvidPlan pair session

EvidPlan keeps an evidence-backed work plan next to its progress journal. `evidplan/plan.py` validates dependency waves, `store.py` persists receipts, and `resume.py` determines the next safe work after interruption.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_validate_and_document`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why invalid plans reach the scheduler and cycle checks stall on blocked work.

## Pt 2 `test_progress_journal_roundtrip`

Persist the JSON plan and its append-only progress journal.

## Pt 3 `test_resume_after_artifact_changes`

Work out which proofs still close their items after an artifact revision.

## Pt 4 `test_online_progress_markdown`

Update a resumable Markdown progress view as worker receipts arrive.

## Pt 5 `test_split_proofs_and_resolver_dependencies`

Split proof obligations and preserve irreversible prerequisites.
