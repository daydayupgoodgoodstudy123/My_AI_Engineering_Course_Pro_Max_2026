"""Original interview practice for 02-ml-fundamentals/04-decision-trees.

Local source: phases/02-ml-fundamentals/04-decision-trees/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math
from collections import Counter

def gini(labels):
    if not labels:
        return 0
    counts = Counter(labels)
    return 1 - sum(((n / len(labels)) ** 2 for n in counts.values()))

def entropy(probabilities):
    if not probabilities or any((p < 0 or p > 1 for p in probabilities)) or abs(sum(probabilities) - 1) > 1e-09:
        raise ValueError('distribution')
    return -sum((p * math.log2(p) for p in probabilities if p))
