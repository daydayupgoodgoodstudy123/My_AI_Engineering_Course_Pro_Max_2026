"""Original interview practice for 05-nlp-foundations-to-advanced/16-text-generation-pre-transformer.

Local source: phases/05-nlp-foundations-to-advanced/16-text-generation-pre-transformer/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math
import json
from collections import Counter

def perplexity(probabilities):
    if not probabilities or any((not 0 < p <= 1 for p in probabilities)):
        raise ValueError('probabilities')
    return math.exp(-sum((math.log(p) for p in probabilities)) / len(probabilities))

def ngram_counts(tokens, n):
    if type(n) is not int or n <= 0:
        raise ValueError('n')
    return dict(Counter((json.dumps(tokens[i:i + n]) for i in range(len(tokens) - n + 1))))
