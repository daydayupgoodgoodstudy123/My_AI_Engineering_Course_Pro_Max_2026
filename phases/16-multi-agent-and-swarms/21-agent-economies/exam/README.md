# CreditEcon pair session

CreditEcon records exact utility observations, stores synthetic accounting snapshots, and allocates finite coalition credit. It also publishes allocation blocks and audits nested team games.

Write the application code so that every test in `tests/test_parts.py` passes as written. This local exercise uses no network service or external payment.

## Pt 0 Setup

Use Python 3.10+ and pytest (`python3 -m pip install pytest`). Run `python3 -m pytest` from your working copy; all parts start skipped, and `--all-parts` and `--solution` are practice switches for after the staged attempt.

## Pt 1 `test_part1_supplied_credit_and_utility_replay`

Comment out `@pytest.mark.skip(reason="Part 1")`, run pytest, and repair the supplied-credit and complete utility-replay service.

## Pt 2 `test_part2_complete_sqlite_accounting`

Save and reopen the complete ordered accounting snapshot with its exact domain fields.

## Pt 3 `test_part3_exact_sampled_and_completed_reports`

Implement exact allocation, sampled allocation and completed-block reporting.

## Pt 4 `test_part4_actual_sample_block_csv`

Project actual per-agent allocation blocks for the supplied CSV publisher.

## Pt 5 `test_part5_nested_direct_child_team_games`

Audit nested direct-child team games, actual weighted support and each leaf accounting record.
