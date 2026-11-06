"""Original interview practice for 01-math-foundations/14-norms-and-distances.

Local source: phases/01-math-foundations/14-norms-and-distances/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def distance(a, b, metric='l2'):
    """Equal-length numeric vectors: metric l1 gives sum absolute differences; l2 gives Euclidean distance; linf gives maximum absolute difference, or 0 for empty vectors. Unknown metric or unequal lengths raises ValueError."""
    raise NotImplementedError('TODO 1: distance; see PROMPT.md')

def cosine(a, b):
    """Return cosine similarity of equal-length numeric vectors. Define zero-norm or empty-vector similarity as 0. Unequal lengths raise ValueError."""
    raise NotImplementedError('TODO 2: cosine; see PROMPT.md')
