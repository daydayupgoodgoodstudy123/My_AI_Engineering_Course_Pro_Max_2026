"""Original interview practice for 19-capstone-projects/69-end-to-end-rag-system.

Local source: phases/19-capstone-projects/69-end-to-end-rag-system/docs/en.md (sha256 in SCOPE.json).
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

def retrieval_metrics(ranked, relevant, k):
    if type(k) is not int or k <= 0 or len(set(ranked)) != len(ranked):
        raise ValueError('ranking')
    rel = set(relevant)
    top = ranked[:k]
    hits = sum((x in rel for x in top))
    first = next((i for i, x in enumerate(top, 1) if x in rel), None)
    return {'precision': hits / k, 'recall': hits / len(rel) if rel else 0, 'reciprocal_rank': 1 / first if first else 0}
