# regadmit pair session

regadmit is the admission controller between an MCP Registry sync and the route table. `regadmit/evidence.py` reads what the Registry says about a listed server version and fingerprints a live tool set, `regadmit/ledger.py` keeps the hash-chained admission ledger, in memory and as a JSON-lines file whose head is anchored somewhere else, and `regadmit/admission.py` runs the admission controls and pins what passes. After admission, `regadmit/reconcile.py` keeps checking admitted versions as observations arrive and streams one NDJSON verdict per observation, and `regadmit/rollback.py` restores routing from what the ledger proves. `regadmit/service.py` wires these together. The Registry, the artifact verifier and the live endpoints are plain data that the tests script.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_evidence_and_ledger`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the evidence helpers and the ledger fail.

## Pt 2 `test_ledger_file`

Keep the ledger in a file, and catch what the hash chain cannot catch by itself.

## Pt 3 `test_admission_controls`

Decide whether one server version is admitted, and pin it.

## Pt 4 `test_reconcile_stream`

Keep checking admitted versions as observations come in.

## Pt 5 `test_rollback_from_history`

Roll back to what the ledger proves is safe.
