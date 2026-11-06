# ReactLoop pair session

ReactLoop is a small agent runtime built on the ReAct loop. `reactloop/loop.py` runs the loop over a native-reasoning model: the model reads the message buffer (`reactloop/messages.py`), asks for tools from the registry (`reactloop/tools.py`), and the loop feeds each result back as an observation until a stop condition fires. The model is a scripted stand-in (`reactloop/model.py`), so everything runs offline. `reactloop/transcript.py` saves runs, `reactloop/react.py` drives prompt-based models that write their steps as text, `reactloop/stream.py` streams a run to the UI, and `reactloop/formatter.py` turns tool results into observations.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_agent_loop`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the loop fails.

## Pt 2 `test_transcript_snapshot`

Save a run's transcript, so that it can be debugged and continued later.

## Pt 3 `test_react_text`

Run the loop with a model that writes its steps as ReAct text.

## Pt 4 `test_stream_events`

Stream a run to the UI as it happens, with the reasoning on its own channel.

## Pt 5 `test_nested_observation`

Turn nested tool results into observations the model can read.
