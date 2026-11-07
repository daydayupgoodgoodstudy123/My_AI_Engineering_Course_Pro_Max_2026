# MindTrace pair session

MindTrace replays visible observations, stores independent observation and belief histories, and makes explicit subject predictions. It also projects ordered model changes and answers bounded queries through nested model contexts.

Write the application code so that every test in `tests/test_parts.py` passes as written. This finite local replay uses no real model or network service.

## Pt 0 Setup

Use Python 3.10+ and pytest (`python3 -m pip install pytest`). Run `python3 -m pytest` from your working copy; every part starts skipped, and `--all-parts` and `--solution` are practice switches for after the staged attempt.

## Pt 1 `test_visible_writer_completion_and_complete_joint_control`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and repair the observation and joint-control replay.

## Pt 2 `test_complete_observation_and_independent_belief_history_sqlite`

Save and reopen complete observation and independent belief-version histories with each agent’s completion state.

## Pt 3 `test_interpret_other_models_predict_perceived_domain_and_choose_actual`

Interpret subject models, predict their targets and choose an own target.

## Pt 4 `test_ordered_observer_local_actual_json_patch_projection`

Project ordered model deltas for the supplied JSON Patch publisher.

## Pt 5 `test_finite_higher_order_current_context_interpreter`

Resolve bounded belief queries through their actual successive model contexts.
