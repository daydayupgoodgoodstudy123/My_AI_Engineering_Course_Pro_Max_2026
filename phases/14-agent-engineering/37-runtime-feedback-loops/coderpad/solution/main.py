"""Original interview practice for 14-agent-engineering/37-runtime-feedback-loops.

Local source: phases/14-agent-engineering/37-runtime-feedback-loops/docs/en.md (sha256 in SCOPE.json).
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

def evidence_gate(evidence, required):
    failed = sorted((k for k in set(required) if evidence.get(k) is not True))
    return {'ready': not failed, 'failed': failed}
