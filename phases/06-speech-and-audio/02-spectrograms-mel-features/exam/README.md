# MelKit pair session

MelKit is the feature front end of a small speech stack. Audio becomes log-mel frames (`melkit/features.py`), frames are cached on disk by clip and config (`melkit/cache.py`), deltas and CMVN prepare them for a model (`melkit/deltas.py`, `melkit/cmvn.py`), and front-end settings are layered nested configs (`melkit/config.py`). `melkit/service.py` wires these together for the API layer.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_log_mel_frontend`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the log-mel code fails.

## Pt 2 `test_feature_cache`

Build the feature cache.

## Pt 3 `test_deltas_and_cmvn`

Add delta features and per-utterance normalization.

## Pt 4 `test_online_cmvn`

Normalize a live stream of frames.

## Pt 5 `test_config_merge_and_fingerprint`

Merge layered configs and give each one a fingerprint.
