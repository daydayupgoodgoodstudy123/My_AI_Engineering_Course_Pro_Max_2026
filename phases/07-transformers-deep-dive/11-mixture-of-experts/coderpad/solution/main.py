"""Original interview practice for 07-transformers-deep-dive/11-mixture-of-experts.

Local source: phases/07-transformers-deep-dive/11-mixture-of-experts/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def top_k(scores, k):
    if type(k) is not int or not 0 <= k <= len(scores):
        raise ValueError('k')
    return sorted(range(len(scores)), key=lambda i: (-scores[i], i))[:k]

def softmax(values):
    if not values:
        raise ValueError('empty')
    maximum = max(values)
    weights = [math.exp(x - maximum) for x in values]
    total = sum(weights)
    return [x / total for x in weights]
