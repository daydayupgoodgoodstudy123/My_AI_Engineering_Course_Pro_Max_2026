"""Original interview practice for 05-nlp-foundations-to-advanced/03-word-embeddings-word2vec.

Local source: phases/05-nlp-foundations-to-advanced/03-word-embeddings-word2vec/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math
import json
from collections import Counter

def ngram_counts(tokens, n):
    """n is exact positive int. Return a dict whose keys are JSON strings encoding each token window (json.dumps defaults) and whose values are counts. n>len(tokens) or empty tokens returns {}. Invalid n raises ValueError."""
    raise NotImplementedError('TODO 1: ngram_counts; see PROMPT.md')

def cosine(a, b):
    """Return cosine similarity of equal-length numeric vectors. Define zero-norm or empty-vector similarity as 0. Unequal lengths raise ValueError."""
    raise NotImplementedError('TODO 2: cosine; see PROMPT.md')
