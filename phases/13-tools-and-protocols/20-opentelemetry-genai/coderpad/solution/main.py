"""Original Phase 13 / Lesson 20 CoderPad practice.

Lesson source: 20-opentelemetry-genai/docs/en.md (local course snapshot).
The precise exercise contract is defined in coderpad/PROMPT.md.
Python 3.10+, stdlib only, no network or API keys.
"""
def redact(value, capture_content=False):
    if isinstance(value, dict):
        forbidden = {'authorization', 'token', 'api_key', 'password'} | (set() if capture_content else {'prompt', 'completion', 'content'})
        return {k: '[REDACTED]' if k.casefold() in forbidden else redact(v, capture_content) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, capture_content) for v in value]
    return value

def summarize(spans):
    result = {}
    for s in spans:
        duration = s['end'] - s['start']
        if duration < 0:
            raise ValueError('time')
        r = result.setdefault(s['name'], {'count': 0, 'total_ms': 0, 'max_ms': 0})
        r['count'] += 1
        r['total_ms'] += duration
        r['max_ms'] = max(r['max_ms'], duration)
    return result

def critical_span(spans):
    return min(spans, key=lambda s: (-(s['end'] - s['start']), s['name']))['name'] if spans else None
