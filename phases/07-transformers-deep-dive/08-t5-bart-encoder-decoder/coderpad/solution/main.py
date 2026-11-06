"""Original interview practice for 07-transformers-deep-dive/08-t5-bart-encoder-decoder.

Local source: phases/07-transformers-deep-dive/08-t5-bart-encoder-decoder/docs/en.md (sha256 in SCOPE.json).
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

def masked_probabilities(logits, allowed):
    if not logits or not allowed or any((type(i) is not int or not 0 <= i < len(logits) for i in allowed)) or (len(set(allowed)) != len(allowed)):
        raise ValueError('mask')
    maximum = max((logits[i] for i in allowed))
    weights = {i: math.exp(logits[i] - maximum) for i in allowed}
    total = sum(weights.values())
    return [weights.get(i, 0) / total for i in range(len(logits))]
