# VoiceFrame pair session

VoiceFrame is a small voice agent in the shape of a Pipecat pipeline. Frames (`voiceframe/frames.py`) flow DOWNSTREAM through VAD, STT, LLM, TTS and the transport, and control frames such as a barge-in cancel flow back UPSTREAM (`voiceframe/pipeline.py`). The audio is scripted and the model and the speech synthesizer are plain functions the tests supply, so everything runs offline. Around the pipeline sit call recordings (`voiceframe/recording.py`), turn taking (`voiceframe/turns.py`), a metrics observer (`voiceframe/metrics.py`) and a latency budget check (`voiceframe/budget.py`).

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_barge_in`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the pipeline fails.

## Pt 2 `test_call_recording`

Record every frame of a call to a binary file we can replay later.

## Pt 3 `test_turn_taking`

Decide when the user has finished speaking, and when the bot has to stop.

## Pt 4 `test_metrics_observer`

Count each stage's frames on the data path, second by second, for Prometheus.

## Pt 5 `test_latency_budget`

Add up a voice chain's latency before we ship it.
