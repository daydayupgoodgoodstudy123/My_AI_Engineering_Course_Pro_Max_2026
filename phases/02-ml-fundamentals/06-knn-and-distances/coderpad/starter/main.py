"""Original interview practice for 02-ml-fundamentals/06-knn-and-distances.

Local source: phases/02-ml-fundamentals/06-knn-and-distances/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def nearest(query, points, k):
    """Return indices of the k nearest points by squared Euclidean distance; ties use lower original index. All points must match query dimension. k is an exact int in [0,len(points)], otherwise ValueError. k=0 returns []."""
    raise NotImplementedError('TODO 1: nearest; see PROMPT.md')

def standardize(train, values):
    """Compute mean and population standard deviation from nonempty train, then transform values. If training variance is zero use scale=1. Return {'mean','scale','values'}. Never fit on values; empty train raises ValueError."""
    raise NotImplementedError('TODO 2: standardize; see PROMPT.md')
