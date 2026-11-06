"""Original interview practice for 04-computer-vision/09-image-generation-gans.

Local source: phases/04-computer-vision/09-image-generation-gans/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def cross_entropy(probabilities, target):
    if not probabilities or any((p < 0 or p > 1 for p in probabilities)) or abs(sum(probabilities) - 1) > 1e-09 or (type(target) is not int) or (not 0 <= target < len(probabilities)):
        raise ValueError('contract')
    return -math.log(max(1e-12, probabilities[target]))

def quadratic_gradient(weights, target):
    if len(weights) != len(target):
        raise ValueError('shape')
    return [2 * (w - t) for w, t in zip(weights, target)]
