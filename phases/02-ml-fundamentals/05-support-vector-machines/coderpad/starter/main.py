"""Original interview practice for 02-ml-fundamentals/05-support-vector-machines.

Local source: phases/02-ml-fundamentals/05-support-vector-machines/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def distance(a, b, metric='l2'):
    """Equal-length numeric vectors: metric l1 gives sum absolute differences; l2 gives Euclidean distance; linf gives maximum absolute difference, or 0 for empty vectors. Unknown metric or unequal lengths raises ValueError."""
    raise NotImplementedError('TODO 1: distance; see PROMPT.md')

def nearest(query, points, k):
    """Return indices of the k nearest points by squared Euclidean distance; ties use lower original index. All points must match query dimension. k is an exact int in [0,len(points)], otherwise ValueError. k=0 returns []."""
    raise NotImplementedError('TODO 2: nearest; see PROMPT.md')
