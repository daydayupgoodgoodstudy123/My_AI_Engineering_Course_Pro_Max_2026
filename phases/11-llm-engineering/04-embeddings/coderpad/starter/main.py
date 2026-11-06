"""Original interview practice for 11-llm-engineering/04-embeddings.

Local source: phases/11-llm-engineering/04-embeddings/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def cosine(a, b):
    """Return cosine similarity of equal-length numeric vectors. Define zero-norm or empty-vector similarity as 0. Unequal lengths raise ValueError."""
    raise NotImplementedError('TODO 1: cosine; see PROMPT.md')

def retrieval_metrics(ranked, relevant, k):
    """ranked is a unique document-id list; relevant is a list treated as a set. k exact positive int. Return precision=len(top-k relevant)/k, recall=hits/number of unique relevant (0 if none), reciprocal_rank=1/first relevant rank within top-k (0 if none). Duplicate ranked ids or invalid k raises ValueError."""
    raise NotImplementedError('TODO 2: retrieval_metrics; see PROMPT.md')
