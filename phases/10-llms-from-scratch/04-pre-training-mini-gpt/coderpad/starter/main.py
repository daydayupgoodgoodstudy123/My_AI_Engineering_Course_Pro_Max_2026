"""Original interview practice for 10-llms-from-scratch/04-pre-training-mini-gpt.

Local source: phases/10-llms-from-scratch/04-pre-training-mini-gpt/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def causal_mask(length, window=None):
    """Return length x length booleans where row i may attend column j iff j<=i and, if window provided, i-j<window. length exact int >=0; window None or exact positive int. Invalid configuration raises ValueError."""
    raise NotImplementedError('TODO 1: causal_mask; see PROMPT.md')

def cross_entropy(probabilities, target):
    """Require nonempty nonnegative probabilities summing to 1 within 1e-9 and exact integer target index in range. Return -log(probabilities[target]); use clamp minimum 1e-12. Invalid input raises ValueError."""
    raise NotImplementedError('TODO 2: cross_entropy; see PROMPT.md')
