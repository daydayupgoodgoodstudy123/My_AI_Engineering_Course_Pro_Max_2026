# CTDEGrid pair session

CTDEGrid inspects scripted local policies, saves complete rollout snapshots, and compares declared joint-value functions. It also publishes actual joint transitions and audits nested numeric expressions.

Write the application code so that every test in `tests/test_parts.py` passes as written. This finite local exercise uses no trained model or network service.

## Pt 0 Setup

Use Python 3.10+ and pytest (`python3 -m pip install pytest`). Run `python3 -m pytest` from your working copy; all parts start skipped, and `--all-parts` and `--solution` are practice switches for after the staged attempt.

## Pt 1 `test_part1_local_joint_inspection`

Comment out `@pytest.mark.skip(reason="Part 1")`, run pytest, and repair the complete local-policy inspection.

## Pt 2 `test_part2_complete_binary_rollout`

Save and reopen the complete ordered rollout snapshot, preserving both actors and exact finite local Q values.

## Pt 3 `test_part3_numeric_certificate_and_joint_value`

Implement the declared numeric mixer, structural certificate and joint-value comparison.

## Pt 4 `test_part4_actual_joint_transition_csv`

Project actual joint transitions for the supplied CSV publisher.

## Pt 5 `test_part5_nested_numeric_path_certificates`

Audit nested numeric expressions and their exact per-Q path certificates in declared Q order.
