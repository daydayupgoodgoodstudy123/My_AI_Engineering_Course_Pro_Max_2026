# Normalize provider tool calls

Original interview simulation · 45 minutes · Python 3.10+ · standard library only.
This is independent practice, not an Edison Scientific question or scoring policy.

## Scenario

A service switches between three providers. Implement a canonical call parser and a tool-choice adapter for the frozen fixture formats below.

## Candidate work

Edit only `starter/main.py`. Keep public signatures and supplied helpers intact.
`tests/test_exam.py` and fixtures are provided. You may add your own tests in a new `tests/test_candidate.py`.
Explain your plan briefly, then implement the core before attempting the bonus.

## Core contract

1. normalize(provider, payload) returns [{'id': str, 'name': str, 'arguments': dict}, ...] in source order. Supported providers: 'openai', 'anthropic', 'gemini'. OpenAI payload is {'tool_calls': [{'id': ..., 'function': {'name': ..., 'arguments': JSON_STRING}}]}; Anthropic is {'content': [{'type': 'tool_use', 'id': ..., 'name': ..., 'input': DICT}, or non-tool blocks]}; Gemini is {'parts': [{'functionCall': {'id': ..., 'name': ..., 'args': DICT}}, or non-tool parts]}. A missing list means no calls. Ignore non-tool Anthropic blocks and Gemini parts. Provider-specific outer API envelopes have already been removed.
2. All ids and names must be nonempty strings; arguments must decode to a dict. Any malformed call, malformed JSON, non-list collection, or unsupported provider raises ValueError; do not return partial results. Do not mutate payload.
3. choice(provider, mode, name=None): mode is 'auto', 'none', 'required', or 'force'. OpenAI maps the first three to the same string; force to {'type': 'function', 'function': {'name': name}}. Anthropic maps to {'type': 'auto'|'none'|'any'|'tool'}, with 'name' only for force. Gemini returns {'mode': 'AUTO'|'NONE'|'ANY'}, adding 'allowed_function_names': [name] for force. Force requires a nonempty string name. Other modes ignore name. Invalid provider/mode raises ValueError. These are exercise fixture contracts, not complete or live SDK adapters.

## Bonus contract

unique_calls(calls) removes exact duplicate ids, preserving first occurrence. If the same id has a different name or arguments, raise ValueError. Calls have already been normalized.

## Commands

```bash
python3 run_tests.py --list
python3 run_tests.py --core
python3 run_tests.py --core -k keyword_from_test_name
python3 run_tests.py --bonus
python3 run_tests.py
```

Read the complete contract before starting. All fixture shapes not declared invalid are supplied valid.
There are no undisclosed external-service requirements. At minute 45, save and record the current result.
Use your own timer; the test runner does not enforce a deadline. Locally stored tests and solutions are readable,
so strict mode relies on your self-discipline or a separate interviewer. Do not read `solution/` or `INTERVIEWER.md` during the attempt.
