# SwarmTune pair session

SwarmTune runs allocated numeric optimization jobs, saves complete experiment checkpoints, and applies explicit delayed routing feedback. It also projects actual observations and audits nested ant paths against shared trail state.

Write the application code so that every test in `tests/test_parts.py` passes as written. This finite local replay uses no language model or network service.

## Pt 0 Setup

Use Python 3.10+ and pytest (`python3 -m pip install pytest`). Run `python3 -m pytest` from your working copy; every part starts skipped, and `--all-parts` and `--solution` are practice switches for after the staged attempt.

## Pt 1 `test_part1_numeric_optimizer_replay`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and repair the numeric optimizer replay.

## Pt 2 `test_part2_binary_checkpoint_and_deferred_outcomes`

Save and reopen the complete experiment checkpoint.

## Pt 3 `test_part3_task_roulette_epoch_decay_and_verified_feedback`

Implement task routing, epoch decay and delayed feedback learning.

## Pt 4 `test_part4_actual_iteration_route_and_learning_ndjson`

Project actual optimization, routing and learning observations for the supplied publisher.

## Pt 5 `test_part5_nested_ant_paths_and_shared_epoch_trails`

Audit nested ant paths and their actual shared trail updates, including epoch decay before a rejected first path.
