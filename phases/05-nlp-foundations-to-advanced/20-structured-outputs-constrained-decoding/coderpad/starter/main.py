"""Original interview practice for 05-nlp-foundations-to-advanced/20-structured-outputs-constrained-decoding.

Local source: phases/05-nlp-foundations-to-advanced/20-structured-outputs-constrained-decoding/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def masked_probabilities(logits, allowed):
    """allowed is a list of unique valid indices; return softmax over allowed logits with 0 at every disallowed index. Preserve original output length. Empty allowed, duplicate/out-of-range/non-int index, or empty logits raises ValueError. Use stable exponentiation."""
    raise NotImplementedError('TODO 1: masked_probabilities; see PROMPT.md')

def softmax(values):
    """Return stable softmax probabilities for a nonempty list of finite logits, preserving order. Subtract the maximum before exponentiation. Empty input raises ValueError."""
    raise NotImplementedError('TODO 2: softmax; see PROMPT.md')
