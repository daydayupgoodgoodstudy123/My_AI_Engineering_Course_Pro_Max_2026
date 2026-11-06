"""Original interview practice for 10-llms-from-scratch/04-pre-training-mini-gpt.

Local source: phases/10-llms-from-scratch/04-pre-training-mini-gpt/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def causal_mask(length, window=None):
    if type(length) is not int or length < 0 or (window is not None and (type(window) is not int or window <= 0)):
        raise ValueError('shape')
    return [[j <= i and (window is None or i - j < window) for j in range(length)] for i in range(length)]

def cross_entropy(probabilities, target):
    if not probabilities or any((p < 0 or p > 1 for p in probabilities)) or abs(sum(probabilities) - 1) > 1e-09 or (type(target) is not int) or (not 0 <= target < len(probabilities)):
        raise ValueError('contract')
    return -math.log(max(1e-12, probabilities[target]))
