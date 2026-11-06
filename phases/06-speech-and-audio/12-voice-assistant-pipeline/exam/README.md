# VoiceBot pair session

VoiceBot is the reasoning half of a voice assistant: the audio pipeline hands it a transcript and speaks the text it returns. The LLM's tool calls run through `voicebot/tools.py`, each conversation lives in a SQLite-backed session store (`voicebot/sessions.py`), and `voicebot/agent.py` runs the tool loop for one turn. `voicebot/service.py` wires these together for the pipeline. `voicebot/trace.py` turns the pipeline's event trace into latency reports, and `voicebot/schema.py` checks tool arguments against their JSON schema.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_tool_dispatch`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why tool calls fail.

## Pt 2 `test_session_store`

Build the session store.

## Pt 3 `test_voice_tool_loop`

Run a turn's tool calls until the LLM answers, and make the answer speakable.

## Pt 4 `test_turn_reports`

Report each turn's latency from a live pipeline trace.

## Pt 5 `test_argument_schema`

Check nested tool arguments against their schema.
