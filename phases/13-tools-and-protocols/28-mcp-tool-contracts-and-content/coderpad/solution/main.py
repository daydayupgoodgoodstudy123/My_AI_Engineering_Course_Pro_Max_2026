"""Original Phase 13 / Lesson 28 CoderPad practice.

Lesson source: 28-mcp-tool-contracts-and-content/docs/en.md (local course snapshot).
The precise exercise contract is defined in coderpad/PROMPT.md.
Python 3.10+, stdlib only, no network or API keys.
"""
import base64, binascii

def validate(result, expected_type):
    types = {'object': lambda v: isinstance(v, dict), 'array': lambda v: isinstance(v, list), 'string': lambda v: isinstance(v, str), 'integer': lambda v: type(v) is int, 'number': lambda v: type(v) in (int, float), 'boolean': lambda v: type(v) is bool, 'null': lambda v: v is None}
    if not isinstance(expected_type, str) or expected_type not in types or (not isinstance(result, dict)) or (not isinstance(result.get('content'), list)) or ('isError' in result and type(result['isError']) is not bool):
        raise ValueError('result')
    for b in result['content']:
        if not isinstance(b, dict):
            raise ValueError('block')
        if b.get('type') == 'text' and isinstance(b.get('text'), str):
            continue
        if b.get('type') == 'image' and b.get('mimeType') in ('image/png', 'image/jpeg') and isinstance(b.get('data'), str) and b['data']:
            try:
                base64.b64decode(b['data'], validate=True)
            except (ValueError, binascii.Error):
                raise ValueError('image')
            continue
        raise ValueError('block')
    if result.get('isError') is not True and ('structured' not in result or not types[expected_type](result['structured'])):
        raise ValueError('structured')
    return True

def pages(fetch):
    result = []
    cursor = None
    seen = set()
    while True:
        page = fetch(cursor)
        result.extend(page['items'])
        cursor = page['next']
        if cursor is None:
            return result
        if cursor in seen:
            raise ValueError('cursor cycle')
        seen.add(cursor)
