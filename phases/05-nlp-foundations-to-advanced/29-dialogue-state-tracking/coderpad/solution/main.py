"""Original interview practice for 05-nlp-foundations-to-advanced/29-dialogue-state-tracking.

Local source: phases/05-nlp-foundations-to-advanced/29-dialogue-state-tracking/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import copy

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

def transition(state, target):
    edges = {'queued': {'running', 'canceled'}, 'running': {'waiting', 'completed', 'failed', 'canceled'}, 'waiting': {'running', 'canceled'}}
    if target not in edges.get(state, set()):
        raise ValueError('transition')
    return target
