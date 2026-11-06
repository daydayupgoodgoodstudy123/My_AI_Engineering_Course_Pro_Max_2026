"""Original interview practice for 02-ml-fundamentals/12-hyperparameter-tuning.

Local source: phases/02-ml-fundamentals/12-hyperparameter-tuning/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import itertools

def grid(parameters, limit):
    if type(limit) is not int or limit < 0:
        raise ValueError('limit')
    keys = sorted(parameters)
    return [dict(zip(keys, values)) for values in itertools.islice(itertools.product(*(parameters[k] for k in keys)), limit)]

def top_k(scores, k):
    if type(k) is not int or not 0 <= k <= len(scores):
        raise ValueError('k')
    return sorted(range(len(scores)), key=lambda i: (-scores[i], i))[:k]
