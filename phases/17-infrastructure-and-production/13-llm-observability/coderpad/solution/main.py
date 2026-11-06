"""Original interview practice for 17-infrastructure-and-production/13-llm-observability.

Local source: phases/17-infrastructure-and-production/13-llm-observability/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def profile(events):
    result = {}
    for e in events:
        d = e['end'] - e['start']
        if d < 0:
            raise ValueError('time')
        r = result.setdefault(e['name'], {'count': 0, 'total': 0, 'max': 0})
        r['count'] += 1
        r['total'] += d
        r['max'] = max(r['max'], d)
    return result

def redact(value):
    if isinstance(value, dict):
        return {k: '[REDACTED]' if k.casefold() in {'token', 'password', 'api_key', 'authorization'} else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value
