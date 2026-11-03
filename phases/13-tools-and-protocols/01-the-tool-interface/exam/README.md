# ToolLoop pair session

ToolLoop is a small tool-calling host. Tools live in a registry (`toolloop/tools.py`), their arguments are checked against a minimal JSON Schema subset (`toolloop/schema.py`), and `toolloop/loop.py` runs the four-step loop: describe the tools, let the model decide, execute the calls, observe the results. The model is a scripted stand-in (`toolloop/model.py`), so everything runs offline.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_tool_loop`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the loop fails.

## Pt 2 `test_session_log`

Keep the conversation in a log that survives a crash.

## Pt 3 `test_rule_of_two`

Put the Rule of Two in front of consequential tools.

## Pt 4 `test_trace_stream`

Stream the loop's trace while it runs.

## Pt 5 `test_composite_tools`

Classify tools that are built from other tools.
