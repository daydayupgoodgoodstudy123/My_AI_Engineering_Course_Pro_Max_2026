"""Original interview practice for 01-math-foundations/13-numerical-stability.

Local source: phases/01-math-foundations/13-numerical-stability/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def softmax(values):
    """Return stable softmax probabilities for a nonempty list of finite logits, preserving order. Subtract the maximum before exponentiation. Empty input raises ValueError."""
    raise NotImplementedError('TODO 1: softmax; see PROMPT.md')

def logsumexp(values):
    """For nonempty finite logits return log(sum(exp(x))) using max subtraction. Empty input raises ValueError."""
    raise NotImplementedError('TODO 2: logsumexp; see PROMPT.md')
