"""Original interview practice for 19-capstone-projects/71-classical-metrics.

Local source: phases/19-capstone-projects/71-classical-metrics/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import json
from collections import Counter

def token_f1(reference, answer):
    if not reference or not answer:
        return 1 if not reference and (not answer) else 0
    overlap = sum((Counter(reference) & Counter(answer)).values())
    p = overlap / len(answer)
    r = overlap / len(reference)
    return 2 * p * r / (p + r) if p + r else 0

def ngram_counts(tokens, n):
    if type(n) is not int or n <= 0:
        raise ValueError('n')
    return dict(Counter((json.dumps(tokens[i:i + n]) for i in range(len(tokens) - n + 1))))
