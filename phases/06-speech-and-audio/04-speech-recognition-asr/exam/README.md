# ASRKit pair session

ASRKit is a small speech-recognition backend. An acoustic model (not part of this repo) emits per-frame log-probabilities over a character vocabulary with a CTC blank. `asrkit/ctc.py` decodes them, `asrkit/scoring.py` computes word error rate, `asrkit/store.py` keeps reference transcripts next to every model version's hypotheses, `asrkit/stream.py` decodes live audio, and `asrkit/lattice.py` rescores word lattices. `asrkit/service.py` wires these together for the API layer.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_greedy_and_wer`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why decoding and scoring fail.

## Pt 2 `test_transcript_store`

Build the transcript store.

## Pt 3 `test_prefix_beam_search`

Implement CTC prefix beam search.

## Pt 4 `test_stream_words`

Decode a live stream into word events.

## Pt 5 `test_lattice_nbest`

Find the best transcripts in a word lattice.
