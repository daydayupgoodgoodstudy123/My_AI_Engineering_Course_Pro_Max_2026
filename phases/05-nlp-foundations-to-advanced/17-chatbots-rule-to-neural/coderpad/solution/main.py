"""Original interview practice for 05-nlp-foundations-to-advanced/17-chatbots-rule-to-neural.

Local source: phases/05-nlp-foundations-to-advanced/17-chatbots-rule-to-neural/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import copy

def route_task(routes, query_tokens, role):
    if len({r['name'] for r in routes}) != len(routes):
        raise ValueError('duplicate route')
    scores = [(len(set(r['keywords']) & set(query_tokens)), r['name']) for r in routes if role in r['roles']]
    best = max((s for s, n in scores), default=0)
    names = [n for s, n in scores if s == best]
    return names[0] if best > 0 and len(names) == 1 else None

def update_slots(state, changes):
    allowed = {'cuisine', 'area', 'people'}
    if not set(state) <= allowed or not set(changes) <= allowed:
        raise ValueError('slot')
    result = copy.deepcopy(state)
    for key, value in changes.items():
        if value is None:
            result.pop(key, None)
        else:
            result[key] = copy.deepcopy(value)
    return result
