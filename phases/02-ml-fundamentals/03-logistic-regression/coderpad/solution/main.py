"""Original interview practice for 02-ml-fundamentals/03-logistic-regression.

Local source: phases/02-ml-fundamentals/03-logistic-regression/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def sigmoid(value):
    if value >= 0:
        return 1 / (1 + math.exp(-value))
    exp = math.exp(value)
    return exp / (1 + exp)

def cross_entropy(probabilities, target):
    if not probabilities or any((p < 0 or p > 1 for p in probabilities)) or abs(sum(probabilities) - 1) > 1e-09 or (type(target) is not int) or (not 0 <= target < len(probabilities)):
        raise ValueError('contract')
    return -math.log(max(1e-12, probabilities[target]))
