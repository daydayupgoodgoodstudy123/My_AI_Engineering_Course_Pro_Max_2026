# SmallvilleLab pair session

SmallvilleLab inspects a local population's memory evidence, saves independent agent state, and applies supplied reflection and plan revisions. It also projects simulated calendar observations and executes nested current plans against a shared local world.

Write the application code so that every test in `tests/test_parts.py` passes as written. This finite deterministic replay uses no real model or network service.

## Pt 0 Setup

Use Python 3.10+ and pytest (`python3 -m pip install pytest`). Run `python3 -m pytest` from your working copy; every part starts skipped, and `--all-parts` and `--solution` are practice switches for after the staged attempt.

## Pt 1 `test_population_available_pending_and_complete_query_inspection`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and repair the town inspection pipeline.

## Pt 2 `test_independent_agent_memory_progress_belief_and_plan_directory`

Save and reopen the complete town and its independent agent states.

## Pt 3 `test_composite_rank_grounded_reflection_and_only_affected_plan_revision`

Implement stable memory ranking, grounded reflection updates and affected-plan revision.

## Pt 4 `test_current_plan_calendar_revision_cancellation_and_actual_fields`

Project current plan observations for the supplied simulated calendar publisher.

## Pt 5 `test_nested_current_plan_containment_open_hours_capacity_and_commit`

Execute nested current plans against the declared temporal and physical world constraints, including ancestor containment and separate venue openings.
