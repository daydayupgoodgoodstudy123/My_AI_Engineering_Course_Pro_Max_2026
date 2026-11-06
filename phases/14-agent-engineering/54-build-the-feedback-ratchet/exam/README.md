# Ratchet pair session

Ratchet turns feedback into owned changes with durable artifacts, proof, review and retirement. `actions.py` materializes affected tracks, `ledger.py` retains control history, `retirement.py` reviews evidence, `stream.py` promotes arriving signals, and `lineage.py` resolves control replacement.

The goal is to write application code so every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_owned_feedback_actions`

Comment out `@pytest.mark.skip('Part 1')`, run pytest, and repair action metadata, impacts and review dates.

## Pt 2 `test_control_csv_history`

Use the supplied CSV codec to number every control revision globally and retain complete artifact history across both tracks.

## Pt 3 `test_evidence_before_retirement`

Distinguish keep, review and evidence-supported retirement.

## Pt 4 `test_multisource_ratchet_stream`

Promote complete owned actions as source evidence arrives.

## Pt 5 `test_control_replacement_lineage`

Resolve transitive replacement and retirement fallback for every affected track.
