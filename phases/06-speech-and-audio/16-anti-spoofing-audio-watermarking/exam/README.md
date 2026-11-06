# Provenance pair session

Provenance is a small authenticity service for voice audio. A toy spectral detector scores how synthetic a clip looks (`provenance/detector.py`), every decision goes into a SQLite-backed audit log (`provenance/audit.py`), and the per-sample output of an AudioSeal-style watermark detector is turned into the segments of a clip that carry the watermark (`provenance/localize.py`). `provenance/service.py` wires these together for the API layer. The service also raises alarms on live calls (`provenance/alarm.py`) and follows C2PA-style manifests back to where an audio file came from (`provenance/manifest.py`).

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_spoof_detector`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the detector code fails.

## Pt 2 `test_audit_log`

Build the audit log.

## Pt 3 `test_watermark_localization`

Find the watermarked part of a clip.

## Pt 4 `test_spoof_alarm`

Raise and clear alarms on a live call.

## Pt 5 `test_manifest_chain`

Follow a manifest's ingredients back to where the audio came from.
