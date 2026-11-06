"""Original interview practice for 07-transformers-deep-dive/07-gpt-causal-language-modeling.

Local source: phases/07-transformers-deep-dive/07-gpt-causal-language-modeling/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def causal_mask(length, window=None):
    """Return length x length booleans where row i may attend column j iff j<=i and, if window provided, i-j<window. length exact int >=0; window None or exact positive int. Invalid configuration raises ValueError."""
    raise NotImplementedError('TODO 1: causal_mask; see PROMPT.md')

def perplexity(probabilities):
    """Return exp(-mean(log(p))) for nonempty true-token probabilities, each 0<p<=1. Invalid inputs raise ValueError. Probabilities are not required to sum to 1 because each refers to a different timestep."""
    raise NotImplementedError('TODO 2: perplexity; see PROMPT.md')
