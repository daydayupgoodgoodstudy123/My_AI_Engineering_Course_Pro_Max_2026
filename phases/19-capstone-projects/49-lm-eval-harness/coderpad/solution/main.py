"""Original interview practice for 19-capstone-projects/49-lm-eval-harness.

Local source: phases/19-capstone-projects/49-lm-eval-harness/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def perplexity(probabilities):
    if not probabilities or any((not 0 < p <= 1 for p in probabilities)):
        raise ValueError('probabilities')
    return math.exp(-sum((math.log(p) for p in probabilities)) / len(probabilities))

def retrieval_metrics(ranked, relevant, k):
    if type(k) is not int or k <= 0 or len(set(ranked)) != len(ranked):
        raise ValueError('ranking')
    rel = set(relevant)
    top = ranked[:k]
    hits = sum((x in rel for x in top))
    first = next((i for i, x in enumerate(top, 1) if x in rel), None)
    return {'precision': hits / k, 'recall': hits / len(rel) if rel else 0, 'reciprocal_rank': 1 / first if first else 0}
