# WorkPull swarm desk

WorkPull replays independent local tasks with logical arrival, pull and completion events. Complete the five parts in order, editing only `workpull/` so that the tests pass as written.

## Pt 0 Setup

Use Python 3.10+ and pytest. Run `python3 -m pytest` from your practice copy; all five parts start skipped. The 60-minute budget has not been calibrated with human candidates.

## Pt 1 `test_complete_fifo_replay`

Remove the Part 1 skip and repair the FIFO completion desk. Retain every task's actual result and worker, drain future arrivals and keep the complete event replay responsive.

## Pt 2 `test_append_task_lifecycle_journal`

Append and reopen distinct task definitions and observed lifecycle records, retaining equal-payload tasks. Reconstruct each task's actual phase and worker; binary framing and scalar codecs are supplied.

## Pt 3 `test_specialist_aging_pull_claims`

Implement specialist admission, full-interval priority aging at the pull instant and exclusive claims in declared worker order. Preserve the declared tie order without preempting running work.

## Pt 4 `test_observed_event_frames`

Project each recorded lifecycle phase, including its signed queued priority, into its own event payload. The UTF8 length-frame encoder and async driver are supplied.

## Pt 5 `test_nested_swarm_pool_contracts`

Inspect inherited topic restrictions including empty scope, branch-visible pools and actual completion totals in nested groups. Full worker/pool identities and subtree membership are supplied.
