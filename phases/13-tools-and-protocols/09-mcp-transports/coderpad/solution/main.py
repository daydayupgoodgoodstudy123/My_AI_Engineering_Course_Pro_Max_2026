"""Original Phase 13 / Lesson 09 CoderPad practice.

Lesson source: 09-mcp-transports/docs/en.md (local course snapshot).
The precise exercise contract is defined in coderpad/PROMPT.md.
Python 3.10+, stdlib only, no network or API keys.
"""
import json

def validate(headers, body, allowed_origins):
    groups = {}
    for k, v in headers:
        groups.setdefault(k.lower(), []).append(v)
    if any((v not in allowed_origins for v in groups.get('origin', []))):
        return 'forbidden_origin'
    if any((len(groups.get(k, [])) > 1 for k in ('origin', 'mcp-version', 'mcp-method', 'mcp-name'))):
        return 'duplicate_header'
    expected = {'mcp-version': body['params']['_meta']['protocolVersion'], 'mcp-method': body['method']}
    if body['method'] == 'tools/call':
        expected['mcp-name'] = body['params']['name']
    if any((groups.get(k) != [v] for k, v in expected.items())) or ('mcp-name' in groups and 'mcp-name' not in expected):
        return 'routing_mismatch'
    return 'ok'

def parse_sse(text):
    result = []
    for event in text.split('\n\n'):
        lines = [line[5:].removeprefix(' ') for line in event.splitlines() if line.startswith('data:')]
        if lines:
            result.append(json.loads('\n'.join(lines)))
    return result
