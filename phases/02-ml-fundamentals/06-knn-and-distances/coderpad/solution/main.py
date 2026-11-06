"""Original interview practice for 02-ml-fundamentals/06-knn-and-distances.

Local source: phases/02-ml-fundamentals/06-knn-and-distances/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def nearest(query, points, k):
    if type(k) is not int or not 0 <= k <= len(points) or any((len(p) != len(query) for p in points)):
        raise ValueError('contract')
    return sorted(range(len(points)), key=lambda i: (sum(((a - b) ** 2 for a, b in zip(query, points[i]))), i))[:k]

def standardize(train, values):
    if not train:
        raise ValueError('empty train')
    mean = sum(train) / len(train)
    scale = math.sqrt(sum(((x - mean) ** 2 for x in train)) / len(train)) or 1
    return {'mean': mean, 'scale': scale, 'values': [(x - mean) / scale for x in values]}
