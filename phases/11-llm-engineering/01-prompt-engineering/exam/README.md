# PromptBench pair session

PromptBench is a small prompt-testing service. Named templates and conversations are built in `promptbench/prompts.py`, template versions live in a file-backed bank (`promptbench/bank.py`), and replay responses are scored in `promptbench/scoring.py`. `promptbench/service.py` wires the prompt builders together for the API layer.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_prompt_builders`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the prompt builders fail.

## Pt 2 `test_template_bank_roundtrip`

Build the versioned template bank.

## Pt 3 `test_score_and_compare`

Score replay responses against the rubric, and compare the models.

## Pt 4 `test_stream_scores`

Project each complete replay case into model-score CSV records with score_rows. The CSV codec, header, async publication and source ownership are supplied.

## Pt 5 `test_pattern_scorecard`

Build a scorecard from the nested comparison reports.
