"""Original interview practice for 02-ml-fundamentals/07-unsupervised-learning.

Local source: phases/02-ml-fundamentals/07-unsupervised-learning/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def quantize_codebook(vectors, codebook):
    if not codebook or any((len(c) != len(codebook[0]) for c in codebook)) or any((len(v) != len(codebook[0]) for v in vectors)):
        raise ValueError('codebook')
    return [min(range(len(codebook)), key=lambda i: sum(((a - b) ** 2 for a, b in zip(v, codebook[i])))) for v in vectors]

def distance(a, b, metric='l2'):
    if len(a) != len(b) or metric not in ('l1', 'l2', 'linf'):
        raise ValueError('contract')
    d = [abs(x - y) for x, y in zip(a, b)]
    return sum(d) if metric == 'l1' else math.sqrt(sum((x * x for x in d))) if metric == 'l2' else max(d, default=0)
