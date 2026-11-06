"""Original interview practice for 07-transformers-deep-dive/01-why-transformers.

Local source: phases/07-transformers-deep-dive/01-why-transformers/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def amdahl(serial_fraction, speedup):
    if not 0 <= serial_fraction <= 1 or speedup < 1:
        raise ValueError('parameters')
    return 1 / (serial_fraction + (1 - serial_fraction) / speedup)

def attention(query, keys, values):
    if not query or not keys or len(keys) != len(values) or any((len(k) != len(query) for k in keys)) or (not values[0]) or any((len(v) != len(values[0]) for v in values)):
        raise ValueError('shape')
    scores = [sum((a * b for a, b in zip(query, k))) / math.sqrt(len(query)) for k in keys]
    maximum = max(scores)
    weights = [math.exp(s - maximum) for s in scores]
    total = sum(weights)
    return [sum((w * v[j] for w, v in zip(weights, values))) / total for j in range(len(values[0]))]
