"""Original interview practice for 18-ethics-safety-alignment/03-direct-preference-optimization-family.

Local source: phases/18-ethics-safety-alignment/03-direct-preference-optimization-family/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def dpo_loss(chosen_logp, rejected_logp, reference_margin, beta):
    if beta <= 0:
        raise ValueError('beta')
    z = beta * (chosen_logp - rejected_logp - reference_margin)
    return max(0, -z) + math.log1p(math.exp(-abs(z)))

def cross_entropy(probabilities, target):
    if not probabilities or any((p < 0 or p > 1 for p in probabilities)) or abs(sum(probabilities) - 1) > 1e-09 or (type(target) is not int) or (not 0 <= target < len(probabilities)):
        raise ValueError('contract')
    return -math.log(max(1e-12, probabilities[target]))
