"""Original interview practice for 05-nlp-foundations-to-advanced/02-bag-of-words-tfidf.

Local source: phases/05-nlp-foundations-to-advanced/02-bag-of-words-tfidf/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math
from collections import Counter

def bag_of_words(tokens, vocabulary):
    """Return counts aligned to an ordered vocabulary of unique strings; ignore unknown tokens. Duplicate vocabulary entries raise ValueError. Empty vocabulary returns []. No normalization."""
    raise NotImplementedError('TODO 1: bag_of_words; see PROMPT.md')

def cosine(a, b):
    """Return cosine similarity of equal-length numeric vectors. Define zero-norm or empty-vector similarity as 0. Unequal lengths raise ValueError."""
    raise NotImplementedError('TODO 2: cosine; see PROMPT.md')
