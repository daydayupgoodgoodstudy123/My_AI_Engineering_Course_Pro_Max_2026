"""Original interview practice for 20-recursive-self-improvement/06-self-rewarding-meta-rewarding.

Local source: phases/20-recursive-self-improvement/06-self-rewarding-meta-rewarding/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def dpo_loss(chosen_logp, rejected_logp, reference_margin, beta):
    if beta <= 0:
        raise ValueError('beta')
    z = beta * (chosen_logp - rejected_logp - reference_margin)
    return max(0, -z) + math.log1p(math.exp(-abs(z)))

def calibration_error(confidences, correct, bins):
    if not confidences or len(confidences) != len(correct) or type(bins) is not int or (bins <= 0) or any((not 0 <= p <= 1 for p in confidences)) or any((type(x) is not bool for x in correct)):
        raise ValueError('calibration')
    groups = {}
    for p, c in zip(confidences, correct):
        groups.setdefault(min(bins - 1, int(p * bins)), []).append((p, c))
    return sum((abs(sum((p for p, c in group)) - sum((c for p, c in group))) / len(confidences) for group in groups.values()))
