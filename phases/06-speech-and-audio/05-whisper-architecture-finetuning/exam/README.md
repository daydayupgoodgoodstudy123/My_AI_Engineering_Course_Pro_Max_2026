# LongForm pair session

LongForm transcribes recordings longer than Whisper's 30 s window. `longform/windows.py` plans overlapping 30 s windows and their frame budget, `longform/tokens.py` reads and writes the decoder's special-token text, `longform/stitch.py` joins the words of overlapping windows, and `longform/stream.py` transcribes a live stream. `longform/lora.py` sizes a LoRA fine-tune. `longform/service.py` wires the batch path together for the API layer.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_window_plan`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the window plan fails.

## Pt 2 `test_decoding_roundtrip`

Write decoder sequences as special-token text, and read them back.

## Pt 3 `test_stitch_windows`

Join the transcripts of overlapping windows into one.

## Pt 4 `test_stream_transcript`

Transcribe a live stream, window by window.

## Pt 5 `test_lora_budget`

Count what a LoRA fine-tune trains.
