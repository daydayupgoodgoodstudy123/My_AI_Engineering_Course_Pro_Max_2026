# Voyager pair session

Voyager is a small skill library for a lifelong-learning agent, after the Voyager paper. A skill is Python code that defines `run(world)`, where the world is a plain dict of resources, inventory and flags. `voyager/skills.py` keeps every version of every skill, searches them by description and tag (a library grows to tens of thousands of skills), and runs a skill after its dependencies. `voyager/store.py` saves the library to disk, `voyager/curriculum.py` proposes what to learn next, `voyager/refine.py` runs the iterative refinement loop, and `voyager/lock.py` locks a composed skill to one version of everything it needs. The code writer and the verifier are test doubles, so everything runs offline.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_skill_library`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the library misbehaves.

## Pt 2 `test_store_roundtrip`

Save the library to disk and read it back.

## Pt 3 `test_curriculum`

Propose the next task, just above what the library can already do.

## Pt 4 `test_refinement_stream`

Learn a task by iterative refinement, and stream each round as it ends.

## Pt 5 `test_version_lock`

Lock a composed skill to one version of every skill it needs.
