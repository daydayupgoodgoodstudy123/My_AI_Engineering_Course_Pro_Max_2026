"""Original interview practice for 04-computer-vision/01-image-fundamentals.

Local source: phases/04-computer-vision/01-image-fundamentals/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def transpose(rows):
    """Return a new list-of-lists transpose. Empty input returns []. Ragged rows raise ValueError. A rectangular matrix of empty rows transposes to []."""
    raise NotImplementedError('TODO 1: transpose; see PROMPT.md')

def standardize(train, values):
    """Compute mean and population standard deviation from nonempty train, then transform values. If training variance is zero use scale=1. Return {'mean','scale','values'}. Never fit on values; empty train raises ValueError."""
    raise NotImplementedError('TODO 2: standardize; see PROMPT.md')
