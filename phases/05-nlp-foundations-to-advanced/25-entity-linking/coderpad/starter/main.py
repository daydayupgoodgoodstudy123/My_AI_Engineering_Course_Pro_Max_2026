"""Original interview practice for 05-nlp-foundations-to-advanced/25-entity-linking.

Local source: phases/05-nlp-foundations-to-advanced/25-entity-linking/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def cosine(a, b):
    """Return cosine similarity of equal-length numeric vectors. Define zero-norm or empty-vector similarity as 0. Unequal lengths raise ValueError."""
    raise NotImplementedError('TODO 1: cosine; see PROMPT.md')

def top_k(scores, k):
    """Return the indices of k largest scores, descending score with lower original index ties. k exact int in [0,len(scores)], else ValueError; k=0 returns []."""
    raise NotImplementedError('TODO 2: top_k; see PROMPT.md')
