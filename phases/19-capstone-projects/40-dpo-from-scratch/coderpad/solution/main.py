"""Original interview practice for 19-capstone-projects/40-dpo-from-scratch.

Local source: phases/19-capstone-projects/40-dpo-from-scratch/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def dpo_loss(chosen_logp, rejected_logp, reference_margin, beta):
    if beta <= 0:
        raise ValueError('beta')
    z = beta * (chosen_logp - rejected_logp - reference_margin)
    return max(0, -z) + math.log1p(math.exp(-abs(z)))

def sigmoid(value):
    if value >= 0:
        return 1 / (1 + math.exp(-value))
    exp = math.exp(value)
    return exp / (1 + exp)
