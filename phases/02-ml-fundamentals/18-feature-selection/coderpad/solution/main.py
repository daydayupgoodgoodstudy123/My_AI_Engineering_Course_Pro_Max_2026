"""Original interview practice for 02-ml-fundamentals/18-feature-selection.

Local source: phases/02-ml-fundamentals/18-feature-selection/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def standardize(train, values):
    if not train:
        raise ValueError('empty train')
    mean = sum(train) / len(train)
    scale = math.sqrt(sum(((x - mean) ** 2 for x in train)) / len(train)) or 1
    return {'mean': mean, 'scale': scale, 'values': [(x - mean) / scale for x in values]}

def top_k(scores, k):
    if type(k) is not int or not 0 <= k <= len(scores):
        raise ValueError('k')
    return sorted(range(len(scores)), key=lambda i: (-scores[i], i))[:k]
