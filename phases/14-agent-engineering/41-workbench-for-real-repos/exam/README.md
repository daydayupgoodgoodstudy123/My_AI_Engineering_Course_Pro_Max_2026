# RealRepo pair session

RealRepo measures the agent workbench on a real-feeling repo. The same task runs through a prompt-only pipeline and a workbench-guided one on a small sample app, and the five outcomes are measured from what each run left behind: its feedback records, its diff, its handoff packet and its review (`realrepo/outcomes.py`). The sample app, the task's scope contract and the two scripted runs are in `realrepo/sample.py`.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_measure_outcomes`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the measurements are wrong.

## Pt 2 `test_outcome_store`

Keep every run's outcomes.

## Pt 3 `test_paired_comparison`

Compare the two pipelines, run by run.

## Pt 4 `test_milestone_stream`

Report when each run reaches its milestones, while the runs are still going.

## Pt 5 `test_change_impact`

Work out which tests a change can affect.
