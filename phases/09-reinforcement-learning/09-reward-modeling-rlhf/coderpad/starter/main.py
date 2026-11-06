"""Original interview practice for 09-reinforcement-learning/09-reward-modeling-rlhf.

Local source: phases/09-reinforcement-learning/09-reward-modeling-rlhf/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def dpo_loss(chosen_logp, rejected_logp, reference_margin, beta):
    """Require beta>0. z=beta*(chosen_logp-rejected_logp-reference_margin). Return log(1+exp(-z)) stably as max(0,-z)+log1p(exp(-abs(z))). Inputs are finite scalar log probabilities."""
    raise NotImplementedError('TODO 1: dpo_loss; see PROMPT.md')

def classification(expected, predicted):
    """Require equal-length exact-bool lists. Return tp,fp,fn,tn,precision,recall,f1. A ratio with zero denominator is 0.0. Empty lists are valid; invalid labels raise ValueError."""
    raise NotImplementedError('TODO 2: classification; see PROMPT.md')
