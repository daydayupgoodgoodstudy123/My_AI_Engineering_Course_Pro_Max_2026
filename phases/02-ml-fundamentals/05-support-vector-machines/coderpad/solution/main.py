"""Original interview practice for 02-ml-fundamentals/05-support-vector-machines.

Local source: phases/02-ml-fundamentals/05-support-vector-machines/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def distance(a, b, metric='l2'):
    if len(a) != len(b) or metric not in ('l1', 'l2', 'linf'):
        raise ValueError('contract')
    d = [abs(x - y) for x, y in zip(a, b)]
    return sum(d) if metric == 'l1' else math.sqrt(sum((x * x for x in d))) if metric == 'l2' else max(d, default=0)

def nearest(query, points, k):
    if type(k) is not int or not 0 <= k <= len(points) or any((len(p) != len(query) for p in points)):
        raise ValueError('contract')
    return sorted(range(len(points)), key=lambda i: (sum(((a - b) ** 2 for a, b in zip(query, points[i]))), i))[:k]
