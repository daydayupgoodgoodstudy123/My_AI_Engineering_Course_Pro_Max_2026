# Reflexion pair session

Reflexion is a small harness for verbal reinforcement learning: after a failed trial the agent writes a reflection, episodic memory keeps it (`reflexion/memory.py`), and the next trial starts fresh but sees it. `reflexion/puzzle.py` runs the lesson's toy task this way, `reflexion/learnings.py` keeps reflections in a Markdown learnings file, `reflexion/judge.py` decides each trial with the lesson's three evaluator types, `reflexion/curve.py` reports a learning curve over many tasks, and `reflexion/scope.py` decides which task classes see which reflections. The model is always a scripted fake; nothing here calls a real LLM.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_reflexion_loop`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the agent does not learn from its reflections.

## Pt 2 `test_learnings_file`

Keep the reflections in a learnings file that people can read and edit.

## Pt 3 `test_judge_and_trials`

Judge each trial with the strongest signal available, and run the trials of one task.

## Pt 4 `test_learning_curve`

Run many tasks at once and stream their learning curve.

## Pt 5 `test_scoped_recall`

Decide which reflections a task class gets to see.
