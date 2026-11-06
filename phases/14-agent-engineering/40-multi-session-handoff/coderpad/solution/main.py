"""Original interview practice for 14-agent-engineering/40-multi-session-handoff.

Local source: phases/14-agent-engineering/40-multi-session-handoff/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import copy

def validate_handoff(bundle):
    issues = [k for k in ('objective', 'state', 'next_action') if not isinstance(bundle.get(k), str) or not bundle[k].strip()]
    checks = bundle.get('checks')
    if not isinstance(checks, list) or not checks or any((not isinstance(x, str) or not x.strip() for x in checks)):
        issues.append('checks')
    return sorted(issues)

def compact_memory(records, limit):
    if type(limit) is not int or limit < 0:
        raise ValueError('limit')
    latest = {}
    for r in records:
        if r['id'] not in latest or r['timestamp'] >= latest[r['id']]['timestamp']:
            latest[r['id']] = r
    return copy.deepcopy(sorted(latest.values(), key=lambda r: (-r['timestamp'], r['id']))[:limit])
