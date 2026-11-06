"""Original interview practice for 14-agent-engineering/02-rewoo-plan-and-execute.

Local source: phases/14-agent-engineering/02-rewoo-plan-and-execute/docs/en.md (sha256 in SCOPE.json).
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

def select_context(items, budget):
    if type(budget) is not int or budget < 0 or any((type(x['tokens']) is not int or x['tokens'] < 0 for x in items)):
        raise ValueError('budget')
    result = []
    for item in sorted(items, key=lambda x: (-x['score'], x['id'])):
        if item['tokens'] <= budget:
            result.append(item['id'])
            budget -= item['tokens']
    return result
