"""Original interview practice for 07-transformers-deep-dive/16-speculative-decoding.

Local source: phases/07-transformers-deep-dive/16-speculative-decoding/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def accept_prefix(draft, verified):
    i = 0
    while i < min(len(draft), len(verified)) and draft[i] == verified[i]:
        i += 1
    return {'accepted': draft[:i], 'next': verified[i] if i < len(verified) else None}

def perplexity(probabilities):
    if not probabilities or any((not 0 < p <= 1 for p in probabilities)):
        raise ValueError('probabilities')
    return math.exp(-sum((math.log(p) for p in probabilities)) / len(probabilities))
