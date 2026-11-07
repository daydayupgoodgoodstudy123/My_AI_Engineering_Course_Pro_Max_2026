# CorrJury pair session

CorrJury records local simulated jury trials, saves complete jury configurations, and computes exact reliability for shared-family seat blocks. `corrjury/service.py` connects the sampled evidence, while the archive, projection, and nested audit use the same declared configuration.

Write the application code so that every test in `tests/test_parts.py` passes as written. This finite local adapter uses no real models or network services.

## Pt 0 Setup

Use Python 3.10+ and pytest (`python3 -m pip install pytest`). Run `python3 -m pytest` from your working copy of this folder; every part starts skipped, and `--all-parts` and `--solution` are practice switches for after the staged attempt.

## Pt 1 `test_shared_draw_strict_majority_read_cost_and_ticket_mapping`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and repair the sampled jury pipeline.

## Pt 2 `test_complete_family_and_exposure_json_snapshot`

Save and reopen the complete ordered jury configuration, preserving each declared exposure allocation.

## Pt 3 `test_exact_family_kernel_convolution_and_majority_tail`

Compute the exact correct-seat distribution and strict-majority reliability, including deterministic family factors.

## Pt 4 `test_actual_trial_fields_and_tsv_observations`

Project completed trial observations for the supplied TSV publisher.

## Pt 5 `test_nested_family_multiplicities_and_joint_reliability`

Assemble each nested jury's family seat model and exact reliability audit, including nonvoting coordination layers.
