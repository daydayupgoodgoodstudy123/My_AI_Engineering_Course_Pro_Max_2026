"""Original interview practice for 09-reinforcement-learning/09-reward-modeling-rlhf.

Local source: phases/09-reinforcement-learning/09-reward-modeling-rlhf/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def dpo_loss(chosen_logp, rejected_logp, reference_margin, beta):
    if beta <= 0:
        raise ValueError('beta')
    z = beta * (chosen_logp - rejected_logp - reference_margin)
    return max(0, -z) + math.log1p(math.exp(-abs(z)))

def classification(expected, predicted):
    if len(expected) != len(predicted) or any((type(x) is not bool for x in expected + predicted)):
        raise ValueError('labels')
    tp = sum((a and b for a, b in zip(expected, predicted)))
    fp = sum((not a and b for a, b in zip(expected, predicted)))
    fn = sum((a and (not b) for a, b in zip(expected, predicted)))
    tn = len(expected) - tp - fp - fn
    p = tp / (tp + fp) if tp + fp else 0
    r = tp / (tp + fn) if tp + fn else 0
    return {'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn, 'precision': p, 'recall': r, 'f1': 2 * p * r / (p + r) if p + r else 0}
