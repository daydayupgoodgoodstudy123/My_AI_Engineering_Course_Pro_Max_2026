"""Original interview practice for 04-computer-vision/16-vision-pipeline-capstone.

Local source: phases/04-computer-vision/16-vision-pipeline-capstone/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

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

def latency_report(latencies, deadline):
    if not latencies or any((t < 0 for t in latencies)) or deadline < 0:
        raise ValueError('latency')
    ordered = sorted(latencies)
    n = len(ordered)
    return {'p50': ordered[math.ceil(0.5 * n) - 1], 'p95': ordered[math.ceil(0.95 * n) - 1], 'goodput_fraction': sum((t <= deadline for t in latencies)) / n}
