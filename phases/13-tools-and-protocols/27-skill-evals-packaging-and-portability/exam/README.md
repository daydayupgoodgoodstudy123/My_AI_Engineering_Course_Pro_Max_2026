# SkillEval pair session

SkillEval is a small release harness for one Agent Skill bundle. `skilleval/metrics.py` scores the skill's trigger boundary over repeated runs of labeled cases, and `skilleval/manifest.py` checks an installed copy of the bundle against its SHA-256 manifest. The rest of the package keeps every run's raw observation in a CSV log (`runlog.py`), applies the release gate one layer at a time (`gate.py`), streams repeated-run results to CI as JUnit XML (`junit.py`), and works out what each host really gives the skill's capabilities (`portability.py`). There is no model in the loop: routers and hosts are scripted stand-ins.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_trigger_report_and_install_check`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the trigger report and the install check come out wrong.

## Pt 2 `test_observation_log_roundtrip`

Keep every run's raw observation in a CSV log, exactly.

## Pt 3 `test_release_gate`

Apply the release gate: one verdict per layer, and a release only with a trusted attestation.

## Pt 4 `test_junit_stream`

Stream repeated-run results to CI as JUnit XML while the runs are still going.

## Pt 5 `test_portability_matrix`

Work out each host's verdict from its capability claims and what they depend on.
