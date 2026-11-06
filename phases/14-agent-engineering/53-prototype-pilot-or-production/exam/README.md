# StageGate pair session

StageGate keeps a build's declared learning environment separate from its observed exposure. `stages.py` plans concrete controls and active-user telemetry, `registry.py` saves declarations, `drift.py` checks boundaries, `monitor.py` reports episodes, and `dependencies.py` checks necessary component responsibilities.

The goal is to write application code so every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_deliberate_stage_plan`

Comment out `@pytest.mark.skip('Part 1')`, run pytest, and repair the declared plan and active-audience telemetry.

## Pt 2 `test_stage_registry_roundtrip`

Keep the complete declaration and its four independent technical markers.

## Pt 3 `test_stage_drift_observations`

Report exposure and responsibility drift without automatically relabeling the system.

## Pt 4 `test_stage_drift_stream`

Report new drift episodes immediately while releasing only safe controlled next steps.

## Pt 5 `test_necessary_component_responsibility`

Check the concrete obligations on necessary dependencies and retain useful evidence paths.
