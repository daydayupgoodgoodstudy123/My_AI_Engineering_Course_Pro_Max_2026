# HTNPlan pair session

HTNPlan is a small planning service in the ChatHTN and AlphaEvolve style. A symbolic HTN planner decomposes compound tasks with a method library and asks a scripted LLM only where the library has nothing that works (`htnplan/planner.py`, with operators and methods in `htnplan/domain.py` and the LLM stand-in in `htnplan/llm.py`). Methods, hand-written and learned, are kept in an INI file (`htnplan/library.py`). `htnplan/evolve.py` evolves candidates with an ensemble of mutators and a deterministic evaluator, `htnplan/ensemble.py` runs that ensemble asynchronously and reports every generation, and `htnplan/tree.py` checks a plan's decomposition tree on its own.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_plan_and_learn`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the planner comes back empty-handed.

## Pt 2 `test_method_library`

Keep the method library in an INI file.

## Pt 3 `test_evolve`

Evolve candidates against a deterministic evaluator, reproducibly.

## Pt 4 `test_stream_generations`

Let the mutators work concurrently, and report each generation as it ends.

## Pt 5 `test_task_tree`

Return the decomposition tree behind a plan, and check it independently.
