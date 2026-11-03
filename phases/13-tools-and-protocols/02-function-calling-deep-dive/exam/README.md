# FCBridge pair session

FCBridge keeps one canonical model of tool calling (`fcbridge/canonical.py`) and translates it at the edge for OpenAI, Anthropic and Gemini (`fcbridge/translate.py`). `fcbridge/bridge.py` asks one provider one question and parses the reply into canonical calls, and `fcbridge/limits.py` holds each provider's request limits. Conversations live in a SQLite store (`fcbridge/store.py`) and are rendered back into each provider's request (`fcbridge/render.py`). `fcbridge/probe.py` checks whether the three providers agree, and `fcbridge/strict.py` compiles tool schemas for OpenAI strict mode. Nothing goes over the network: the tests stand in for the three APIs with scripted fakes that check every request.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_edge_translators`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why asking the providers fails.

## Pt 2 `test_conversation_store`

Build the conversation store.

## Pt 3 `test_render_requests`

Render a conversation as each provider's request, within each provider's limits.

## Pt 4 `test_equivalence_probe`

Ask every provider at once, and report each answer as it arrives.

## Pt 5 `test_strict_compiler`

Compile a tool schema for OpenAI strict mode.
