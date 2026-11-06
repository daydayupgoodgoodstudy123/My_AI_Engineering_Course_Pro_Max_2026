# SpeakerID pair session

SpeakerID is a small speaker-recognition service. An upstream model turns each utterance into a fixed-size embedding. The service compares embeddings by cosine similarity (`speakerid/embed.py`), measures verification quality as an equal error rate over a trial list (`speakerid/trials.py`), keeps enrolled speakers in a SQLite-backed registry (`speakerid/registry.py`), and accepts or rejects identity claims (`speakerid/scoring.py`). It also works out who spoke when in a meeting, online while the speech arrives (`speakerid/diarize.py`) or offline from an agglomerative-clustering tree (`speakerid/cluster.py`).

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_trial_list_eer`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the EER code fails.

## Pt 2 `test_enrollment_registry`

Build the speaker registry.

## Pt 3 `test_snorm_verification`

Score identity claims against an imposter cohort, and set the decision threshold.

## Pt 4 `test_online_diarization`

Diarize a meeting while its speech segments arrive.

## Pt 5 `test_dendrogram_cut`

Turn an agglomerative-clustering tree into speaker clusters.
