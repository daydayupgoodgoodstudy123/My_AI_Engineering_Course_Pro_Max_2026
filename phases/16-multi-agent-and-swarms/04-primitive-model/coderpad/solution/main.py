"""Original interview practice for 16-multi-agent-and-swarms/04-primitive-model.

Local source: phases/16-multi-agent-and-swarms/04-primitive-model/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def transition(state, target):
    edges = {'queued': {'running', 'canceled'}, 'running': {'waiting', 'completed', 'failed', 'canceled'}, 'waiting': {'running', 'canceled'}}
    if target not in edges.get(state, set()):
        raise ValueError('transition')
    return target

def route_task(routes, query_tokens, role):
    if len({r['name'] for r in routes}) != len(routes):
        raise ValueError('duplicate route')
    scores = [(len(set(r['keywords']) & set(query_tokens)), r['name']) for r in routes if role in r['roles']]
    best = max((s for s, n in scores), default=0)
    names = [n for s, n in scores if s == best]
    return names[0] if best > 0 and len(names) == 1 else None
