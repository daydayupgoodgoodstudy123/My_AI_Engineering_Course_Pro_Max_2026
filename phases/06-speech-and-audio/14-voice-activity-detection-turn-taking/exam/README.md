# TurnKit pair session

TurnKit decides when the user of a voice agent is talking and when they are done. A cheap energy gate labels 20 ms frames (`turnkit/energy.py`), speech segments are kept in a SQLite table (`turnkit/segments.py`), a state machine turns frame decisions into turns (`turnkit/turns.py`), and a cascade puts the gate in front of an expensive VAD model on live audio (`turnkit/cascade.py`). `turnkit/overlap.py` works out who talks inside whose turn. `turnkit/service.py` wires these together for the agent.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_energy_gate`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the energy gate fails.

## Pt 2 `test_segment_table`

Build the segment table.

## Pt 3 `test_turn_detector`

Decide when a turn starts and ends.

## Pt 4 `test_cascade_stream`

Run the cascade on a live stream.

## Pt 5 `test_overlap_tree`

Work out the structure of a conversation where people talk over each other.
