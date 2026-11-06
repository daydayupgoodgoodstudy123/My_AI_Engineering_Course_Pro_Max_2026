# SpecModes pair session

SpecModes turns six specification surfaces into explicit decision boundaries. The agent may own cheap choices, choose within stated limits, or stop at a human checkpoint. The service preserves the reason for each boundary and checks proof against the actual claim.

The goal is to make every test in `tests/test_parts.py` pass as written. **Time: 60 minutes.** All observations and effects are local deterministic fixtures.

## Pt 0 Setup

You need Python 3.10+ and pytest. In a temporary practice copy run `python -B -m pytest -q -p no:cacheprovider`. Every part starts skipped. Unlock one part at a time without changing assertions, fixtures or timing limits.

## Pt 1 `test_executable_specification`

Repair specification validation and compilation, including the ordered dependency catalog. An explicit exercise rule requires normal, edge, failure and forbidden examples.

## Pt 2 `test_decision_revision_journal`

Implement the append-only JSON Lines decision journal and replay a revision prefix while preserving historic rationale and typed boundaries.

## Pt 3 `test_proof_matches_claim`

Verify required receipts against claim type, identity, finite case coverage and authority scope. Proof types have specific roles; an audit receipt does not automatically replace a wire test.

## Pt 4 `test_private_policy_stream`

Gate controlled action attempts before injected fake effects. Emit private NDJSON continue, stop or checkpoint packets using the supplied serializer.

## Pt 5 `test_boundary_ast`

Evaluate a finite structured boundary AST and return the actual blocking leaf paths. Schema and leaf/unit helpers are supplied; no natural-language parser is required.
