"""Original interview practice for 02-ml-fundamentals/07-unsupervised-learning.

Local source: phases/02-ml-fundamentals/07-unsupervised-learning/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def quantize_codebook(vectors, codebook):
    """Codebook must be a nonempty set of same-dimensional numeric rows. All vectors must have that dimension. Return nearest codeword index per vector by squared Euclidean distance, ties to lower index. Invalid dimensions or empty codebook raises ValueError."""
    raise NotImplementedError('TODO 1: quantize_codebook; see PROMPT.md')

def distance(a, b, metric='l2'):
    """Equal-length numeric vectors: metric l1 gives sum absolute differences; l2 gives Euclidean distance; linf gives maximum absolute difference, or 0 for empty vectors. Unknown metric or unequal lengths raises ValueError."""
    raise NotImplementedError('TODO 2: distance; see PROMPT.md')
