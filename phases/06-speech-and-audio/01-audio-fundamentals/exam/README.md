# WavLab pair session

WavLab is the audio intake in front of our speech models. Uploads arrive as 16-bit PCM (`wavlab/pcm.py`) and are kept in the archive as WAV files (`wavlab/wavfile.py`). `wavlab/spectrum.py` looks for test tones and hum, `wavlab/resample.py` brings live 48 kHz streams down to the recognizer's 16 kHz, and `wavlab/riff.py` reads the chunks inside WAV files.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_pcm16_codec`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the PCM code fails.

## Pt 2 `test_wav_roundtrip`

Write WAV files for the archive, and read them back.

## Pt 3 `test_dominant_frequency`

Find the strongest tone in a clip.

## Pt 4 `test_stream_downsample`

Downsample a live stream as it arrives.

## Pt 5 `test_riff_walk`

Walk the chunk tree of a RIFF file.
