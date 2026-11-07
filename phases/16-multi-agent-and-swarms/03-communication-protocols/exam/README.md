# AuditMesh pair session

AuditMesh records a delegated operation and exposes a structural audit. `auditmesh/capture.py` and `ownership.py` capture private receipts, `repository.py` stores their ordered observations, and `gateway.py` applies local trust and output policies.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest. Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_single_execution_and_private_audit`

Comment out `@pytest.mark.skip('Part 1')`, run pytest, and repair execution capture and private audit receipts.

## Pt 2 `test_ordered_sqlite_observations`

Store and reopen complete runs with their ordered observations.

## Pt 3 `test_trust_modality_and_shared_projection`

Apply local admission and output rules, then produce the task and public audit.

## Pt 4 `test_audit_domain_events_and_seal`

Build observation patches and a coherent terminal audit through the supplied SSE driver.

## Pt 5 `test_structural_did_relationships`

Inspect key-purpose references in a local DID document.

The checks include scoped run order, independent public snapshots, full sealed observation content, and simultaneous DID findings.
