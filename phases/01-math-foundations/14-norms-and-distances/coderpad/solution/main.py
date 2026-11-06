"""Original interview practice for 01-math-foundations/14-norms-and-distances.

Local source: phases/01-math-foundations/14-norms-and-distances/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def distance(a, b, metric='l2'):
    if len(a) != len(b) or metric not in ('l1', 'l2', 'linf'):
        raise ValueError('contract')
    d = [abs(x - y) for x, y in zip(a, b)]
    return sum(d) if metric == 'l1' else math.sqrt(sum((x * x for x in d))) if metric == 'l2' else max(d, default=0)

def cosine(a, b):
    if len(a) != len(b):
        raise ValueError('shape')
    den = math.sqrt(sum((x * x for x in a)) * sum((y * y for y in b)))
    return sum((x * y for x, y in zip(a, b))) / den if den else 0
