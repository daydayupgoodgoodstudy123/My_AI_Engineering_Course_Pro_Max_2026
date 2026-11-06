"""Original interview practice for 05-nlp-foundations-to-advanced/15-topic-modeling.

Local source: phases/05-nlp-foundations-to-advanced/15-topic-modeling/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math
from collections import Counter

def bag_of_words(tokens, vocabulary):
    if len(set(vocabulary)) != len(vocabulary):
        raise ValueError('duplicate vocabulary')
    counts = Counter(tokens)
    return [counts[t] for t in vocabulary]

def entropy(probabilities):
    if not probabilities or any((p < 0 or p > 1 for p in probabilities)) or abs(sum(probabilities) - 1) > 1e-09:
        raise ValueError('distribution')
    return -sum((p * math.log2(p) for p in probabilities if p))
