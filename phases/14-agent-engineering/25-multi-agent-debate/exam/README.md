# Debate pair session

Debate runs multi-agent debates the way Society of Minds does: N debaters propose answers, read each other over R rounds, and converge. `debate/protocol.py` is the runner ported from the lesson (full mesh and star); `debate/transcript.py` stores a debate in a binary file; `debate/engine.py` runs a debate over any read topology; `debate/live.py` runs one against slow async models and reports each round as CSV; and `debate/topology.py` analyzes a topology before any model is called. Every model in the tests is a scripted fake.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_lesson_runner`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the lesson's runner fails.

## Pt 2 `test_transcript_roundtrip`

Save a debate transcript in the binary layout, and load it back.

## Pt 3 `test_sparse_debate`

Run a debate over any topology, with distinct openings and a confidence-weighted answer.

## Pt 4 `test_live_rounds`

Ask every debater in a round at once, and report each round as soon as it ends.

## Pt 5 `test_topology_analysis`

Work out what a topology costs and how far answers travel through it.
