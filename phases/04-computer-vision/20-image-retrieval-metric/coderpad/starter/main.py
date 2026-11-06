"""Original interview practice for 04-computer-vision/20-image-retrieval-metric.

Local source: phases/04-computer-vision/20-image-retrieval-metric/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def distance(a, b, metric='l2'):
    """Equal-length numeric vectors: metric l1 gives sum absolute differences; l2 gives Euclidean distance; linf gives maximum absolute difference, or 0 for empty vectors. Unknown metric or unequal lengths raises ValueError."""
    raise NotImplementedError('TODO 1: distance; see PROMPT.md')

def retrieval_metrics(ranked, relevant, k):
    """ranked is a unique document-id list; relevant is a list treated as a set. k exact positive int. Return precision=len(top-k relevant)/k, recall=hits/number of unique relevant (0 if none), reciprocal_rank=1/first relevant rank within top-k (0 if none). Duplicate ranked ids or invalid k raises ValueError."""
    raise NotImplementedError('TODO 2: retrieval_metrics; see PROMPT.md')
