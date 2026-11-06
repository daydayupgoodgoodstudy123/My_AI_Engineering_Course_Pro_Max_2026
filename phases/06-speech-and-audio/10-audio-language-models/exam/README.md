# LALMKit pair session

LALMKit is the code around an audio-language model (audio encoder → projector → LLM decoder). `lalmkit/inputs.py` turns a prompt with audio slots into decoder inputs and padded batches, `lalmkit/results.py` keeps the raw outputs of benchmark runs, and `lalmkit/mcq.py` scores MMAU-style multiple-choice answers; `lalmkit/service.py` wires those two together for the eval runner. `lalmkit/context.py` keeps a live conversation inside the context budget, and `lalmkit/messages.py` flattens chat messages for the processor.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_decoder_inputs`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the input code fails.

## Pt 2 `test_result_store`

Store the raw outputs of benchmark runs.

## Pt 3 `test_score_multiple_choice`

Score free-text answers to multiple-choice questions, per category.

## Pt 4 `test_live_context`

Keep a live audio and text conversation inside the context budget.

## Pt 5 `test_flatten_messages`

Flatten nested chat messages for the processor.
