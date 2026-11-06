"""Original interview practice for 00-setup-and-tooling/05-jupyter-notebooks.

Local source: phases/00-setup-and-tooling/05-jupyter-notebooks/docs/en.md (sha256 in SCOPE.json).
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

def summary(values):
    if not values:
        raise ValueError('empty')
    mean = sum(values) / len(values)
    return {'mean': mean, 'variance': sum(((x - mean) ** 2 for x in values)) / len(values), 'min': min(values), 'max': max(values)}
