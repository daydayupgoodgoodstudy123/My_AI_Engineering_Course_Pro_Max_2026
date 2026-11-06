"""Original interview practice for 20-recursive-self-improvement/17-alignment-anchor-preservation.

Local source: phases/20-recursive-self-improvement/17-alignment-anchor-preservation/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def normalize(values):
    norm = math.sqrt(sum((x * x for x in values)))
    if norm == 0:
        raise ValueError('zero norm')
    return [x / norm for x in values]

def dot(a, b):
    if len(a) != len(b):
        raise ValueError('shape')
    return sum((x * y for x, y in zip(a, b)))
