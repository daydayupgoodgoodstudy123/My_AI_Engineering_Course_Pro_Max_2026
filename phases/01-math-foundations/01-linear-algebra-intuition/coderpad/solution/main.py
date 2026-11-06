"""Original interview practice for 01-math-foundations/01-linear-algebra-intuition.

Local source: phases/01-math-foundations/01-linear-algebra-intuition/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def dot(a, b):
    if len(a) != len(b):
        raise ValueError('shape')
    return sum((x * y for x, y in zip(a, b)))

def normalize(values):
    norm = math.sqrt(sum((x * x for x in values)))
    if norm == 0:
        raise ValueError('zero norm')
    return [x / norm for x in values]
