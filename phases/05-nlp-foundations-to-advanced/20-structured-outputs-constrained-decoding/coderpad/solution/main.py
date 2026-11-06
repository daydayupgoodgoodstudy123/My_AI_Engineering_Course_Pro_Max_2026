"""Original interview practice for 05-nlp-foundations-to-advanced/20-structured-outputs-constrained-decoding.

Local source: phases/05-nlp-foundations-to-advanced/20-structured-outputs-constrained-decoding/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def masked_probabilities(logits, allowed):
    if not logits or not allowed or any((type(i) is not int or not 0 <= i < len(logits) for i in allowed)) or (len(set(allowed)) != len(allowed)):
        raise ValueError('mask')
    maximum = max((logits[i] for i in allowed))
    weights = {i: math.exp(logits[i] - maximum) for i in allowed}
    total = sum(weights.values())
    return [weights.get(i, 0) / total for i in range(len(logits))]

def softmax(values):
    if not values:
        raise ValueError('empty')
    maximum = max(values)
    weights = [math.exp(x - maximum) for x in values]
    total = sum(weights)
    return [x / total for x in weights]
