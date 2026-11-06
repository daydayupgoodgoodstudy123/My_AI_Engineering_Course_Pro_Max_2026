"""Original interview practice for 07-transformers-deep-dive/07-gpt-causal-language-modeling.

Local source: phases/07-transformers-deep-dive/07-gpt-causal-language-modeling/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def causal_mask(length, window=None):
    if type(length) is not int or length < 0 or (window is not None and (type(window) is not int or window <= 0)):
        raise ValueError('shape')
    return [[j <= i and (window is None or i - j < window) for j in range(length)] for i in range(length)]

def perplexity(probabilities):
    if not probabilities or any((not 0 < p <= 1 for p in probabilities)):
        raise ValueError('probabilities')
    return math.exp(-sum((math.log(p) for p in probabilities)) / len(probabilities))
