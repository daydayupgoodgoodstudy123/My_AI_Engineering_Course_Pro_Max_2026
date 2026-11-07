# SpeechAct pair session

SpeechAct translates local request fixtures into a finite ACL-style envelope. `speechact/translation.py` selects intent and language labels, `codec.py` writes the wire, and `service.py` contains receiving consumers. A journal records messages; conversation reports, envelope framing and typed content live in separate modules.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_translation_and_complete_acl_wire`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and repair the complete translation and wire exchange.

## Pt 2 `test_append_acl_journal`

Append and reopen complete messages with exact labels and typed empty payloads. Reads observe later appends; tagged payload values and binary framing are supplied.

## Pt 3 `test_local_speech_act_obligations`

Recognize the two declared local interaction automata and report each named obligation. Both reply parties and terminal stages remain binding.

## Pt 4 `test_incremental_acl_envelopes`

Frame complete envelopes across decoded text chunks; only whitespace may appear between envelopes. UTF8 decoding, asynchronous publication and source closure are supplied.

## Pt 5 `test_typed_nested_content`

Parse and render the finite typed content tree, preserving repeated children and bare atom spelling. The lexical cursor is supplied; no logical interpretation or evaluation is requested.
