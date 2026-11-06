"""Original interview practice for 07-transformers-deep-dive/15-attention-variants.

Local source: phases/07-transformers-deep-dive/15-attention-variants/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def causal_mask(length, window=None):
    if type(length) is not int or length < 0 or (window is not None and (type(window) is not int or window <= 0)):
        raise ValueError('shape')
    return [[j <= i and (window is None or i - j < window) for j in range(length)] for i in range(length)]

def top_k(scores, k):
    if type(k) is not int or not 0 <= k <= len(scores):
        raise ValueError('k')
    return sorted(range(len(scores)), key=lambda i: (-scores[i], i))[:k]
