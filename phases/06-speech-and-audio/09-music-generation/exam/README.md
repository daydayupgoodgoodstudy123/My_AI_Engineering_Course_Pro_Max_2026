# MusicBox pair session

MusicBox is a small symbolic music-generation backend. A prompt becomes a chord-and-drum piece rendered as MIDI-style notes on a tick grid (`musicbox/theory.py`, `musicbox/compose.py`), generated tracks live in a SQLite store together with their tempo map (`musicbox/store.py`), generations are scored against a reference set with Fréchet Audio Distance (`musicbox/fad.py`), a live player receives bars while the model is still writing (`musicbox/stream.py`), and song forms are expanded into one timeline (`musicbox/form.py`). `musicbox/service.py` wires these together for the API layer.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_prompt_to_notes`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the composer fails.

## Pt 2 `test_track_store`

Build the track store.

## Pt 3 `test_frechet_audio_distance`

Score generations against a reference set, and rank models by it.

## Pt 4 `test_stream_bars`

Send a live generation to the player, bar by bar.

## Pt 5 `test_song_form`

Expand a song form into one timeline.
