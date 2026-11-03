# SkillCat pair session

SkillCat is the skill layer of an agent host. It finds Agent Skills packages in the configured scopes and settles name collisions by each scope's rank (`skillcat/discovery.py`), keeps a skill's reads inside its own package (`skillcat/resources.py`), and publishes the compact catalog the model sees (`skillcat/catalog.py`). Around that core it caches discovery between sessions in a JSON snapshot (`skillcat/cache.py`), fits the catalog into its share of the context window (`skillcat/budget.py`), logs every activation and read of a session as logfmt (`skillcat/disclosure.py`), and maps what each `SKILL.md` links to (`skillcat/refgraph.py`). `skillcat/service.py` wires these together for the runtime.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_discovery_pipeline`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the host cannot build its catalog.

## Pt 2 `test_discovery_cache`

Remember what discovery found, so the next session only looks at what changed.

## Pt 3 `test_catalog_budget`

Fit the catalog into the session's context window.

## Pt 4 `test_disclosure_log`

Serve a session's activations and reads, and log each one as it happens.

## Pt 5 `test_reference_graph`

Map what a skill's `SKILL.md` can reach, and how far away it is.
