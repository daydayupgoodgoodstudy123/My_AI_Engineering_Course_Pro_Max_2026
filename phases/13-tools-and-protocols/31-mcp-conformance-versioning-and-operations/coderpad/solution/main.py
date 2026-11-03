"""Original Phase 13 / Lesson 31 CoderPad practice.

Lesson source: 31-mcp-conformance-versioning-and-operations/docs/en.md (local course snapshot).
The precise exercise contract is defined in coderpad/PROMPT.md.
Python 3.10+, stdlib only, no network or API keys.
"""
import json

def compare(raw, sdk, capabilities):
    allowed = {'complete'} | ({'input_required'} if 'input' in capabilities else set()) | ({'task'} if 'tasks' in capabilities else set())
    if not isinstance(raw.get('resultType'), str) or raw['resultType'] not in allowed:
        raise ValueError('resultType')
    for key, value in raw.items():
        if not key.startswith('x-') and (key not in sdk or json.dumps(value, sort_keys=True) != json.dumps(sdk[key], sort_keys=True)):
            raise ValueError('normalization loss')
    return True

def release(report):
    reasons = []
    t = report.get('transcripts')
    if not isinstance(t, list) or not t or any((v is not True for v in t)):
        reasons.append('transcripts')
    if report.get('redacted') is not True:
        reasons.append('redacted')
    if report.get('rollback_tested') is not True:
        reasons.append('rollback')
    h = report.get('health')
    valid = isinstance(h, dict) and type(h.get('requests')) is int and (h['requests'] > 0) and (type(h.get('errors')) is int) and (0 <= h['errors'] <= h['requests']) and (type(h.get('p95_ms')) in (int, float)) and (h['p95_ms'] >= 0)
    if not valid or h['errors'] / h['requests'] > 0.01 or h['p95_ms'] > 500:
        reasons.append('health')
    return {'ready': not reasons, 'reasons': sorted(reasons)}

def failure_rate(report):
    h = report.get('health')
    if not isinstance(h, dict) or type(h.get('requests')) is not int or h['requests'] <= 0 or (type(h.get('errors')) is not int) or (not 0 <= h['errors'] <= h['requests']):
        raise ValueError('counts')
    return h['errors'] / h['requests']
