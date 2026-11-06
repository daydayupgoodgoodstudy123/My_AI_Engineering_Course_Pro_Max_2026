"""Original interview practice for 12-multimodal-ai/04-flamingo-gated-cross-attention.

Local source: phases/12-multimodal-ai/04-flamingo-gated-cross-attention/docs/en.md (sha256 in SCOPE.json).
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

def flow_step(state, velocity, delta):
    if len(state) != len(velocity) or not 0 <= delta <= 1:
        raise ValueError('contract')
    return [x + delta * v for x, v in zip(state, velocity)]
