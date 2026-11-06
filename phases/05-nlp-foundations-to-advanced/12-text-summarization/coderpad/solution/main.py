"""Original interview practice for 05-nlp-foundations-to-advanced/12-text-summarization.

Local source: phases/05-nlp-foundations-to-advanced/12-text-summarization/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
from collections import Counter

def token_f1(reference, answer):
    if not reference or not answer:
        return 1 if not reference and (not answer) else 0
    overlap = sum((Counter(reference) & Counter(answer)).values())
    p = overlap / len(answer)
    r = overlap / len(reference)
    return 2 * p * r / (p + r) if p + r else 0

def retrieval_metrics(ranked, relevant, k):
    if type(k) is not int or k <= 0 or len(set(ranked)) != len(ranked):
        raise ValueError('ranking')
    rel = set(relevant)
    top = ranked[:k]
    hits = sum((x in rel for x in top))
    first = next((i for i, x in enumerate(top, 1) if x in rel), None)
    return {'precision': hits / k, 'recall': hits / len(rel) if rel else 0, 'reciprocal_rank': 1 / first if first else 0}
