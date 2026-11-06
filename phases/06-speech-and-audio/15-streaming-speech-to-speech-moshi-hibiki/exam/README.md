# Duplex pair session

Duplex is a small full-duplex speech-to-speech backend in the shape of Moshi. Audio is coded as Mimi-style tokens, 8 codes per 80 ms frame (`duplex/mimi.py`), and every step a toy model hears one frame of the user and speaks one frame of its own (`duplex/model.py`). Sessions are logged frame by frame (`duplex/log.py`), the model's words become its inner-monologue text stream (`duplex/monologue.py`), live sessions are watched from both directions (`duplex/monitor.py`), and frames are laid out with Moshi's acoustic delay (`duplex/delay.py`). `duplex/service.py` wires these together for the API layer.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_duplex_step`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the duplex loop fails.

## Pt 2 `test_session_log`

Build the session log.

## Pt 3 `test_inner_monologue`

Lay the model's words onto its text stream.

## Pt 4 `test_session_timeline`

Merge a live session's uplink and downlink, frame by frame.

## Pt 5 `test_acoustic_delay`

Lay frames out with the acoustic delay, and back.
