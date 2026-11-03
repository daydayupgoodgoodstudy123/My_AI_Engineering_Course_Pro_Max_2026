"""Original Phase 13 / Lesson 04 CoderPad practice.

Lesson source: 04-structured-output/docs/en.md (local course snapshot).
The precise exercise contract is defined in coderpad/PROMPT.md.
Python 3.10+, stdlib only, no network or API keys.
"""
import json

def extract(raw, refusal=None):
    if refusal is not None:
        return {'kind': 'refusal', 'reason': refusal}
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        return {'kind': 'parse_error'}
    if not isinstance(value, dict) or set(value) != {'title', 'score'}:
        return {'kind': 'schema_error'}
    title, score = (value['title'], value['score'])
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 80 or type(score) is not int or (not 0 <= score <= 5):
        return {'kind': 'schema_error'}
    return {'kind': 'ok', 'value': {'title': title.strip(), 'score': score}}

def extract_many(rows):
    items = [extract(r['raw'], r.get('refusal')) for r in rows]
    return {'items': items, 'ok_count': sum((x['kind'] == 'ok' for x in items))}
