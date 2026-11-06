"""Original interview practice for 04-computer-vision/20-image-retrieval-metric.

Local source: phases/04-computer-vision/20-image-retrieval-metric/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def distance(a, b, metric='l2'):
    if len(a) != len(b) or metric not in ('l1', 'l2', 'linf'):
        raise ValueError('contract')
    d = [abs(x - y) for x, y in zip(a, b)]
    return sum(d) if metric == 'l1' else math.sqrt(sum((x * x for x in d))) if metric == 'l2' else max(d, default=0)

def retrieval_metrics(ranked, relevant, k):
    if type(k) is not int or k <= 0 or len(set(ranked)) != len(ranked):
        raise ValueError('ranking')
    rel = set(relevant)
    top = ranked[:k]
    hits = sum((x in rel for x in top))
    first = next((i for i, x in enumerate(top, 1) if x in rel), None)
    return {'precision': hits / k, 'recall': hits / len(rel) if rel else 0, 'reciprocal_rank': 1 / first if first else 0}
