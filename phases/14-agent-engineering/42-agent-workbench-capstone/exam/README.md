# WBPack pair session

WBPack installs a versioned agent workbench into another repository. `wbpack/install.py` owns the installer, `manifest.py` pins package files, and `upgrade.py` plans releases without overwriting local work.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_install_contract`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why installation fails.

## Pt 2 `test_manifest_roundtrip`

Store and verify a package manifest.

## Pt 3 `test_release_and_three_way_upgrade`

Classify a release and plan a three-way upgrade.

## Pt 4 `test_incremental_install_log`

Apply installation operations and stream their progress.

## Pt 5 `test_component_reference_closure`

Resolve the components needed by a partial pack.
