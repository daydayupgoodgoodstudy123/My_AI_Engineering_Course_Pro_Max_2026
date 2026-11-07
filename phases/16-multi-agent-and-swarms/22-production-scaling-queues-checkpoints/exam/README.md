# OutboxFlow — Durable Outbox and Nested Admin Queues

Original offline interview practice for Phase 16 / Lesson 22. Suggested duration: 60 minutes; this budget has not been calibrated with human candidates. Python 3.10+, standard library and pytest.

Maintain a local durable-execution service with checkpoint recovery, an independent idempotent receiver, runtime-version bindings and nested group queues. Complete the five parts in order; later parts consume the earlier implementations.

## Pt 1 — Checkpoints and queues

Repair checkpoint selection and the queue response lifecycle, then handle the complete FIFO burst without losing or changing outputs. Follow the existing consumers and preserve the stated acknowledgement contract.

## Pt 2 — Durable domain records

Implement checkpoint, intent and actual receipt storage under the caller's transaction. Preserve each record's full run identity, fields and pending association through close and reopen.

## Pt 3 — Commit, dispatch and recover

Implement atomic checkpoint/intent composition, independent delivery followed by acknowledgement, and recovery at the declared crash cuts. Use the supplied receiver contract and the repaired earlier parts.

## Pt 4 — Rainbow deployment CSV

Project the declared deployment events into CSV rows. Keep each run's original runtime binding and report the relevant version's active count and retirement permission.

## Pt 5 — Nested admin routes

Audit every declared nested route, boundary export declaration and requested-run outbound output. Use the complete supplied address, mailbox and origin binding, and consume the earlier durable delivery result.

## Working rules

Edit the candidate modules in `outboxflow/`; keep the supplied support code and test assertions intact. Remove only the active Part's skip decorator when unlocking it, and keep later parts locked.

Start with [使用说明.md](使用说明.md). Keep `solution/` and `INTERVIEWER.md` closed during an independent attempt; use [REVIEW_TEMPLATE.md](REVIEW_TEMPLATE.md) afterward. The local filesystem does not enforce a timer or hide answers.

The local FIFO workload and timing boundary are recorded in SCOPE.json; preserve the complete-output contract when changing the implementation.
