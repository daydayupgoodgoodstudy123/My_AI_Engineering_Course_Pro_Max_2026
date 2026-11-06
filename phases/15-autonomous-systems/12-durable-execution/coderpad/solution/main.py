"""Original interview practice for 15-autonomous-systems/12-durable-execution.

Local source: phases/15-autonomous-systems/12-durable-execution/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import json

def replay_requests(requests):
    seen = {}
    executed = []
    replayed = []
    for r in requests:
        payload = json.dumps(r['payload'], sort_keys=True, separators=(',', ':'))
        if r['id'] in seen:
            if seen[r['id']] != payload:
                raise ValueError('conflict')
            replayed.append(r['id'])
        else:
            seen[r['id']] = payload
            executed.append(r['id'])
    return {'executed': executed, 'replayed': replayed}

def validate_handoff(bundle):
    issues = [k for k in ('objective', 'state', 'next_action') if not isinstance(bundle.get(k), str) or not bundle[k].strip()]
    checks = bundle.get('checks')
    if not isinstance(checks, list) or not checks or any((not isinstance(x, str) or not x.strip() for x in checks)):
        issues.append('checks')
    return sorted(issues)
