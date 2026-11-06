"""Original interview practice for 07-transformers-deep-dive/11-mixture-of-experts.

Local source: phases/07-transformers-deep-dive/11-mixture-of-experts/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def top_k(scores, k):
    """Return the indices of k largest scores, descending score with lower original index ties. k exact int in [0,len(scores)], else ValueError; k=0 returns []."""
    raise NotImplementedError('TODO 1: top_k; see PROMPT.md')

def softmax(values):
    """Return stable softmax probabilities for a nonempty list of finite logits, preserving order. Subtract the maximum before exponentiation. Empty input raises ValueError."""
    raise NotImplementedError('TODO 2: softmax; see PROMPT.md')
