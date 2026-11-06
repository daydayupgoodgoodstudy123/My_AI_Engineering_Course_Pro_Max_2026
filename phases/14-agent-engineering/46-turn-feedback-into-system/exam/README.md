# Promote pair session

Promote turns observed agent corrections into durable controls. `promote/controls.py` groups causes and chooses an owning layer, `records.py` keeps the ratchet record, `causes.py` compares proposed controls, `stream.py` watches recurring corrections, and `chain.py` places a control in an explicit why-graph.

The goal is to write the application code so every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_correction_pipeline`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why corrections reach the wrong control or lose their evidence.

## Pt 2 `test_ratchet_record_roundtrip`

Keep each control's full ratchet record between sessions.

## Pt 3 `test_cause_not_symptom`

Choose an effective control for each identified cause, rather than repeating the symptom.

## Pt 4 `test_online_promotion`

Promote a recurring or severe correction while observations arrive.

## Pt 5 `test_effective_owner_in_why_graph`

Place controls at effective owners in a shared why-graph.
