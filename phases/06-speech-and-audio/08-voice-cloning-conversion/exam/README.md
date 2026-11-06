# CloneGate pair session

CloneGate is a small voice-conversion service that will only clone a voice its owner agreed to. Consents live in a SQLite registry (`clonegate/consent.py`), speech is converted frame by frame with kNN-VC (`clonegate/knnvc.py`), and every output is stamped with a blind spread-spectrum watermark that carries the consent id (`clonegate/watermark.py`). `clonegate/service.py` wires these together for the API layer.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_watermark_roundtrip`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why stamped clips fail verification.

## Pt 2 `test_consent_registry`

Build the consent registry.

## Pt 3 `test_convert_with_consent`

Convert a voice, but only with consent.

## Pt 4 `test_watch_stream`

Watch a live stream for the watermark.

## Pt 5 `test_policy_decisions`

Decide requests against nested consent policies, and say which rule said no.
