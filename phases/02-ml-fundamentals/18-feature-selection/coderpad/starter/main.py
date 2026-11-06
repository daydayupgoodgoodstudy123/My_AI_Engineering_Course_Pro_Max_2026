"""Original interview practice for 02-ml-fundamentals/18-feature-selection.

Local source: phases/02-ml-fundamentals/18-feature-selection/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def standardize(train, values):
    """Compute mean and population standard deviation from nonempty train, then transform values. If training variance is zero use scale=1. Return {'mean','scale','values'}. Never fit on values; empty train raises ValueError."""
    raise NotImplementedError('TODO 1: standardize; see PROMPT.md')

def top_k(scores, k):
    """Return the indices of k largest scores, descending score with lower original index ties. k exact int in [0,len(scores)], else ValueError; k=0 returns []."""
    raise NotImplementedError('TODO 2: top_k; see PROMPT.md')
