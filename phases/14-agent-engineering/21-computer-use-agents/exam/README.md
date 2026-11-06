# ComputerUse pair session

ComputerUse is a toy computer-use agent. A screen is a list of labeled elements at pixel coordinates (`computeruse/screen.py`), a `FakeDesktop` stands in for the virtual display and its mouse and keyboard (`computeruse/desktop.py`), and a per-step safety classifier judges every action before it runs (`computeruse/safety.py`). `computeruse/agent.py` is the agent loop. Nothing calls a real model or the network: the tests script every action.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_agent_loop`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the agent loop misbehaves.

## Pt 2 `test_capture_roundtrip`

Keep every step's screenshot outside the trace, stored by content.

## Pt 3 `test_safety_service`

Build the per-step safety service for a session that moves across pages.

## Pt 4 `test_trace_stream`

Trace a long unattended run, one line per step, as it happens.

## Pt 5 `test_hit_test_tree`

Find what a click from a scaled-down screenshot lands on in a nested UI tree.
