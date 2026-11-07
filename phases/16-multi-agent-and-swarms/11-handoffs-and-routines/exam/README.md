# RoutineHop caller desk

RoutineHop records local routine handoffs, executes owner-bound tool batches and preserves caller continuations. Complete the five parts in order, editing only `routinehop/` so that the tests pass as written.

## Pt 0 Setup

Use Python 3.10+ and pytest. Run `python3 -m pytest` from your practice copy; all five parts start skipped. The 60-minute budget has not been calibrated with human candidates.

## Pt 1 `test_refund_receipt_and_last_k_guard`

Remove the Part 1 skip and repair refund intake, outgoing handoff receipts and the online last-three-handoff guard. Preserve the complete replay while keeping its processing responsive.

## Pt 2 `test_caller_snapshot_and_runtime_rebinding`

Persist and reopen complete caller continuations, including ordered receipts and request IDs. Rebind the saved active routine through the supplied runtime catalog.

## Pt 3 `test_owner_bound_batch_control_returns`

Bind each batch to its original routine and distinguish genuine Agent returns from ordinary data. Transfer on the first control return and record the remaining calls as skipped without invoking them.

## Pt 4 `test_typed_routine_receipt_ndjson`

Project each typed receipt's own domain fields into public NDJSON records. Classification, JSON encoding and async publication are supplied.

## Pt 5 `test_nested_independent_caller_runs`

Compose sequential own batches with independent nested caller runs. Preserve each caller's own active routine, history and declared step structure.
