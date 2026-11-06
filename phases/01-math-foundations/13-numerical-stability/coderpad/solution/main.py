"""Original interview practice for 01-math-foundations/13-numerical-stability.

Local source: phases/01-math-foundations/13-numerical-stability/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def softmax(values):
    if not values:
        raise ValueError('empty')
    maximum = max(values)
    weights = [math.exp(x - maximum) for x in values]
    total = sum(weights)
    return [x / total for x in weights]

def logsumexp(values):
    if not values:
        raise ValueError('empty')
    m = max(values)
    return m + math.log(sum((math.exp(x - m) for x in values)))
