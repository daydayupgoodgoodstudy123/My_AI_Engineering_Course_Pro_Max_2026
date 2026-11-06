"""Original interview practice for 18-ethics-safety-alignment/03-direct-preference-optimization-family.

Local source: phases/18-ethics-safety-alignment/03-direct-preference-optimization-family/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def dpo_loss(chosen_logp, rejected_logp, reference_margin, beta):
    """Require beta>0. z=beta*(chosen_logp-rejected_logp-reference_margin). Return log(1+exp(-z)) stably as max(0,-z)+log1p(exp(-abs(z))). Inputs are finite scalar log probabilities."""
    raise NotImplementedError('TODO 1: dpo_loss; see PROMPT.md')

def cross_entropy(probabilities, target):
    """Require nonempty nonnegative probabilities summing to 1 within 1e-9 and exact integer target index in range. Return -log(probabilities[target]); use clamp minimum 1e-12. Invalid input raises ValueError."""
    raise NotImplementedError('TODO 2: cross_entropy; see PROMPT.md')
