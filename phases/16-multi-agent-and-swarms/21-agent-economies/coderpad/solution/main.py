"""Original interview practice for 16-multi-agent-and-swarms/21-agent-economies.

Local source: phases/16-multi-agent-and-swarms/21-agent-economies/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import json

def budget_decisions(costs, limit):
    if limit < 0 or any((c < 0 for c in costs)):
        raise ValueError('budget')
    spent = 0
    accepted = []
    for cost in costs:
        allow = spent + cost <= limit
        accepted.append(allow)
        if allow:
            spent += cost
    return {'accepted': accepted, 'spent': spent}

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
