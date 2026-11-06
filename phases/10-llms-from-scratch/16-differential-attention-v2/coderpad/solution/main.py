"""Original interview practice for 10-llms-from-scratch/16-differential-attention-v2.

Local source: phases/10-llms-from-scratch/16-differential-attention-v2/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def attention(query, keys, values):
    if not query or not keys or len(keys) != len(values) or any((len(k) != len(query) for k in keys)) or (not values[0]) or any((len(v) != len(values[0]) for v in values)):
        raise ValueError('shape')
    scores = [sum((a * b for a, b in zip(query, k))) / math.sqrt(len(query)) for k in keys]
    maximum = max(scores)
    weights = [math.exp(s - maximum) for s in scores]
    total = sum(weights)
    return [sum((w * v[j] for w, v in zip(weights, values))) / total for j in range(len(values[0]))]

def layer_norm(values, epsilon=1e-05):
    if not values or epsilon <= 0:
        raise ValueError('contract')
    mean = sum(values) / len(values)
    variance = sum(((x - mean) ** 2 for x in values)) / len(values)
    return [(x - mean) / math.sqrt(variance + epsilon) for x in values]
