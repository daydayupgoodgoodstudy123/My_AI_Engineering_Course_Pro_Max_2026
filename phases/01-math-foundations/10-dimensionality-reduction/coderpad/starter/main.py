"""Original interview practice for 01-math-foundations/10-dimensionality-reduction.

Local source: phases/01-math-foundations/10-dimensionality-reduction/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def eigenvalues_2x2(matrix):
    """Require a 2x2 numeric matrix. Return its two real eigenvalues sorted ascending. A negative discriminant or invalid shape raises ValueError. Repeated eigenvalues appear twice."""
    raise NotImplementedError('TODO 1: eigenvalues_2x2; see PROMPT.md')

def standardize(train, values):
    """Compute mean and population standard deviation from nonempty train, then transform values. If training variance is zero use scale=1. Return {'mean','scale','values'}. Never fit on values; empty train raises ValueError."""
    raise NotImplementedError('TODO 2: standardize; see PROMPT.md')
