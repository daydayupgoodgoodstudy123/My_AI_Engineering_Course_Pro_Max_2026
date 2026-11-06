"""Original interview practice for 15-autonomous-systems/01-long-horizon-agents.

Local source: phases/15-autonomous-systems/01-long-horizon-agents/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


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

def transition(state, target):
    edges = {'queued': {'running', 'canceled'}, 'running': {'waiting', 'completed', 'failed', 'canceled'}, 'waiting': {'running', 'canceled'}}
    if target not in edges.get(state, set()):
        raise ValueError('transition')
    return target
