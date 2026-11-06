# ReWOO pair session

ReWOO is a small plan-then-execute agent runtime. The planner writes the whole plan up front: each step names a tool and its arguments, and refers to earlier evidence as `#E1`, `#E2`, and so on. Workers run the steps in dependency order and collect their evidence (`rewoo/workers.py`), and the solver composes the answer from it (`rewoo/agent.py`). `rewoo/dataset.py` keeps teacher plans for distilling a small planner, `rewoo/replan.py` adds a Plan-and-Execute replanner, `rewoo/stream.py` runs a plan while the planner is still writing it, and `rewoo/nested.py` expands sub-plans into one flat plan.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_run_plan`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the solver ends up with the wrong evidence.

## Pt 2 `test_plan_dataset`

Keep the teacher's plans as a dataset for fine-tuning a small planner.

## Pt 3 `test_replan`

When some evidence is unusable, replan only the part of the plan that depends on it.

## Pt 4 `test_stream_plan`

Run each step as soon as the planner has written it and its evidence is ready.

## Pt 5 `test_flatten`

Expand sub-plans, which name their evidence their own way, into one flat plan.
