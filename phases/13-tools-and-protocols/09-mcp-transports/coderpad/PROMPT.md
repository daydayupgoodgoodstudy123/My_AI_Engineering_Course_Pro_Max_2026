# Check transport routing headers

Original interview simulation · 45 minutes · Python 3.10+ · standard library only.
This is independent practice, not an Edison Scientific question or scoring policy.

## Scenario

A proxy can accidentally route a request using headers that disagree with its body. Implement the pre-forwarding check.

## Candidate work

Edit only `starter/main.py`. Keep public signatures and supplied helpers intact.
`tests/test_exam.py` and fixtures are provided. You may add your own tests in a new `tests/test_candidate.py`.
Explain your plan briefly, then implement the core before attempting the bonus.

## Core contract

validate(headers, body, allowed_origins) returns 'ok', 'forbidden_origin', 'duplicate_header', or 'routing_mismatch', in that priority order. headers is a list of (name,value) strings; compare names case-insensitively. If Origin is present, every Origin value must exactly match an allowed origin; absent Origin is accepted. Duplicate Origin or any duplicate mcp-version, mcp-method, mcp-name returns duplicate_header. Require exactly one mcp-version equal to body['params']['_meta']['protocolVersion'] and mcp-method equal to body['method']. For tools/call require mcp-name equal to body['params']['name']; for other methods mcp-name must be absent. Body envelopes are valid. No URL normalization, session header, or real HTTP server is required.

## Bonus contract

parse_sse(text) reads blank-line-delimited SSE events, ignores comment lines starting ':', joins multiple 'data:' lines with newline, JSON-decodes data, and returns payloads in order. Ignore events without data. Invalid JSON raises ValueError. Input uses LF newlines and ends on an event boundary.

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
