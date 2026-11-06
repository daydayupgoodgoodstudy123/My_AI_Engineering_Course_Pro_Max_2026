"""Original interview practice for 02-ml-fundamentals/03-logistic-regression.

Local source: phases/02-ml-fundamentals/03-logistic-regression/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def sigmoid(value):
    """Return logistic sigmoid for a finite scalar, avoiding overflow for large positive or negative magnitudes."""
    raise NotImplementedError('TODO 1: sigmoid; see PROMPT.md')

def cross_entropy(probabilities, target):
    """Require nonempty nonnegative probabilities summing to 1 within 1e-9 and exact integer target index in range. Return -log(probabilities[target]); use clamp minimum 1e-12. Invalid input raises ValueError."""
    raise NotImplementedError('TODO 2: cross_entropy; see PROMPT.md')
