# Orchestra pair session

Orchestra is a small multi-agent orchestration service. A supervisor (`orchestra/supervisor.py`) asks a routing LLM which of its members should take a task, and a member can be a worker or another supervisor. The whole topology of workers and teams is kept as configuration (`orchestra/topology.py`). Around it sit a planner that nests supervisors only as deep as their context budget forces (`orchestra/budget.py`), tool-call supervision over JSON-RPC 2.0 (`orchestra/rpc.py`), and deterministic keyword routing down the nested teams (`orchestra/routing.py`). Routers and specialists are plain Python objects that the tests supply, so everything runs offline.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_supervisor_routing`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the supervisors misroute.

## Pt 2 `test_topology_snapshot`

Save the topology as a JSON snapshot that reads back exactly as it was configured, and that a failed save cannot damage.

## Pt 3 `test_budgeted_hierarchy`

Nest supervisors when one prompt cannot hold every specialist, and only then.

## Pt 4 `test_tool_call_supervision`

Call the specialists as tools over JSON-RPC, and decide what each one sees.

## Pt 5 `test_hierarchical_routing`

Route tasks down the nested teams without an LLM, backing out of dead ends, and trace every pick.
