# conformance pair session

conformance is a small MCP conformance harness for the `2026-07-28` wire and the earlier initialization era. `conformance/evidence.py` hashes evidence and redacts secrets out of it, `conformance/release.py` decides whether a candidate release is promoted, rolled back or held, `conformance/corpus.py` keeps golden and negative transcript fixtures on disk, `conformance/validate.py` judges recorded responses against the wire rules, `conformance/proxy.py` stitches a proxy's ingress, origin and egress captures, and `conformance/differential.py` compares a raw result with the view an SDK hands the application. `conformance/wire.py` holds the wire constants and the rule names.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_release_gate`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the release gate lets through evidence it should refuse.

## Pt 2 `test_transcript_corpus`

Store transcript fixtures, one file per case.

## Pt 3 `test_response_conformance`

Judge recorded responses, then run the whole corpus through the release gate.

## Pt 4 `test_proxy_tap`

Stitch proxy captures as they arrive and report every exchange as TAP.

## Pt 5 `test_sdk_differential`

Find every way an SDK's view differs from the wire.
