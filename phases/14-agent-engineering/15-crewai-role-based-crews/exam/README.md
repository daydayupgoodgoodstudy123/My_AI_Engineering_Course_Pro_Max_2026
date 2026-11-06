# CrewFlow pair session

CrewFlow is a small CrewAI-shaped toolkit. Agents and tasks run as a sequential crew (`crewflow/crew.py`) with short- and long-term memory (`crewflow/memory.py`), and a Flow wires plain Python steps together by topic (`crewflow/flow.py`). Every model behind an agent is a scripted stand-in (`crewflow/llm.py`) that answers in order or by prompt, so everything runs offline. `crewflow/entities.py` keeps facts about customers, `crewflow/hierarchy.py` runs the hierarchical process with a manager, `crewflow/events.py` is the async Flow that production logs come from, and `crewflow/rundiff.py` compares two runs.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_crew_and_flow`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the crew fails.

## Pt 2 `test_entity_memory`

Remember facts about customers across kickoffs.

## Pt 3 `test_hierarchical_routing`

Let a manager route the crew, and keep the editor waiting for a real draft.

## Pt 4 `test_flow_event_log`

Run the Flow asynchronously, and log every step as it completes.

## Pt 5 `test_run_diff`

Show on-call where a bad run left a good one.
