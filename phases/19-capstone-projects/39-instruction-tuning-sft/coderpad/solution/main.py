"""Original interview practice for 19-capstone-projects/39-instruction-tuning-sft.

Local source: phases/19-capstone-projects/39-instruction-tuning-sft/docs/en.md (sha256 in SCOPE.json).
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

def cross_entropy(probabilities, target):
    if not probabilities or any((p < 0 or p > 1 for p in probabilities)) or abs(sum(probabilities) - 1) > 1e-09 or (type(target) is not int) or (not 0 <= target < len(probabilities)):
        raise ValueError('contract')
    return -math.log(max(1e-12, probabilities[target]))
