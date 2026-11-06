"""Original interview practice for 03-deep-learning-core/05-loss-functions.

Local source: phases/03-deep-learning-core/05-loss-functions/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def cross_entropy(probabilities, target):
    """Require nonempty nonnegative probabilities summing to 1 within 1e-9 and exact integer target index in range. Return -log(probabilities[target]); use clamp minimum 1e-12. Invalid input raises ValueError."""
    raise NotImplementedError('TODO 1: cross_entropy; see PROMPT.md')

def mse(predicted, expected):
    """Return mean squared error of equal-length nonempty numeric lists. Unequal lengths or empty inputs raise ValueError."""
    raise NotImplementedError('TODO 2: mse; see PROMPT.md')
