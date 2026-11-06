# CoTBallot pair session

CoTBallot is a small math-prompt service. Worked examples are selected and formatted in `cotballot/examples.py`, a SQLite corpus lives in `cotballot/bank.py`, and replayed reasoning samples are counted in `cotballot/ballot.py`. `cotballot/service.py` wires the prompt builders together for the API layer.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_worked_example_pipeline`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the worked-example pipeline fails.

## Pt 2 `test_example_bank_roundtrip`

Build the example bank.

## Pt 3 `test_self_consistency_ballot`

Count the final answers from the replay samples.

## Pt 4 `test_stream_running_ballots`

Build each cumulative ballot event in ballot_event. The async source driver, per-stream history and source ownership are supplied.

## Pt 5 `test_thought_trace_accounting`

Inspect the supplied thought trace and account for its paths and usage.
