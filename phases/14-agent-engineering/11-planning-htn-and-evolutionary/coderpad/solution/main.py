"""Original interview practice for 14-agent-engineering/11-planning-htn-and-evolutionary.

Local source: phases/14-agent-engineering/11-planning-htn-and-evolutionary/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def topological_order(dependencies):
    pending = {n: set(ds) for n, ds in dependencies.items()}
    for ds in dependencies.values():
        for name in ds:
            pending.setdefault(name, set())
    result = []
    while pending:
        ready = sorted((n for n, ds in pending.items() if not ds))
        if not ready:
            raise ValueError('cycle')
        n = ready[0]
        result.append(n)
        del pending[n]
        for ds in pending.values():
            ds.discard(n)
    return result

def pareto_front(candidates):
    return sorted((a['id'] for a in candidates if not any((b['quality'] >= a['quality'] and b['cost'] <= a['cost'] and (b['quality'] > a['quality'] or b['cost'] < a['cost']) for b in candidates))))
