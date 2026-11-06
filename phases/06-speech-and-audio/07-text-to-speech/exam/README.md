# TTSFront pair session

TTSFront is the text side of a small text-to-speech service. Written text becomes spoken words (`ttsfront/normalize.py`) and then ARPAbet phones (`ttsfront/g2p.py`). Known words come from a SQLite pronunciation lexicon (`ttsfront/lexicon.py`), and each phone's predicted duration becomes whole mel frames (`ttsfront/duration.py`). `ttsfront/stream.py` cuts streaming LLM text into chunks the synthesizer can start on, `ttsfront/ssml.py` flattens SSML markup, and `ttsfront/service.py` wires these together for the API layer.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_text_frontend`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the frontend fails.

## Pt 2 `test_lexicon_roundtrip`

Build the pronunciation lexicon.

## Pt 3 `test_frame_allocation`

Turn predicted durations into mel frames.

## Pt 4 `test_speech_events`

Feed the synthesizer while the LLM is still writing.

## Pt 5 `test_ssml_flatten`

Flatten SSML markup into segments.
