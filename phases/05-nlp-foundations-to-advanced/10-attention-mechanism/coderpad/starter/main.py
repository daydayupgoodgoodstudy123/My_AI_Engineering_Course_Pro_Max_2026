"""Original interview practice for 05-nlp-foundations-to-advanced/10-attention-mechanism.

Local source: phases/05-nlp-foundations-to-advanced/10-attention-mechanism/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def attention(query, keys, values):
    """query is nonempty length d; keys is nonempty NxD and values is NxV with nonempty equal row widths. Compute softmax(query dot key / sqrt(d)) then the weighted sum of value rows. Invalid shapes raise ValueError; implement with Python lists."""
    raise NotImplementedError('TODO 1: attention; see PROMPT.md')

def softmax(values):
    """Return stable softmax probabilities for a nonempty list of finite logits, preserving order. Subtract the maximum before exponentiation. Empty input raises ValueError."""
    raise NotImplementedError('TODO 2: softmax; see PROMPT.md')
