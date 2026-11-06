# EvalSuite pair session

EvalSuite is a small audio-evaluation harness. Transcripts are normalized and scored as WER, or CER for languages written without spaces (`evalsuite/scoring.py`). Results go on a SQLite leaderboard (`evalsuite/board.py`), two systems are compared with a paired bootstrap (`evalsuite/bootstrap.py`), running error rates stream out while an eval job runs (`evalsuite/stream.py`), and a nested benchmark suite rolls up into scores (`evalsuite/suite.py`). `evalsuite/service.py` wires these together for the eval jobs.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_normalized_scoring`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the scoring code fails.

## Pt 2 `test_leaderboard`

Build the leaderboard.

## Pt 3 `test_paired_bootstrap`

Find out whether one system really beats another on the same test set.

## Pt 4 `test_stream_report`

Report running error rates while results arrive.

## Pt 5 `test_suite_scores`

Score a nested benchmark suite.
