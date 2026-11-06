"""Original interview practice for 02-ml-fundamentals/08-feature-engineering.

Local source: phases/02-ml-fundamentals/08-feature-engineering/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math
from collections import Counter

def standardize(train, values):
    if not train:
        raise ValueError('empty train')
    mean = sum(train) / len(train)
    scale = math.sqrt(sum(((x - mean) ** 2 for x in train)) / len(train)) or 1
    return {'mean': mean, 'scale': scale, 'values': [(x - mean) / scale for x in values]}

def bag_of_words(tokens, vocabulary):
    if len(set(vocabulary)) != len(vocabulary):
        raise ValueError('duplicate vocabulary')
    counts = Counter(tokens)
    return [counts[t] for t in vocabulary]
