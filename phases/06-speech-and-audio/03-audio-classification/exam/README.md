# ClipTag pair session

ClipTag is a small audio-tagging service. A clip becomes a vector of pooled MFCCs (`cliptag/features.py`), labeled clips live in a SQLite-backed bank (`cliptag/bank.py`), and new audio is tagged by k-nearest neighbours (`cliptag/classify.py`). `cliptag/service.py` wires these together for the API layer.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_feature_pipeline`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the feature code fails.

## Pt 2 `test_bank_roundtrip`

Build the clip bank.

## Pt 3 `test_classify_and_evaluate`

Tag clips against the bank, and measure how well we do on the eval split.

## Pt 4 `test_stream_labels`

Tag a live stream, window by window.

## Pt 5 `test_ontology_rollup`

Roll scores up the label ontology.
