"""Original interview practice for 14-agent-engineering/18-agno-and-mastra-runtimes.

Local source: phases/14-agent-engineering/18-agno-and-mastra-runtimes/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def transition(state, target):
    edges = {'queued': {'running', 'canceled'}, 'running': {'waiting', 'completed', 'failed', 'canceled'}, 'waiting': {'running', 'canceled'}}
    if target not in edges.get(state, set()):
        raise ValueError('transition')
    return target

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
