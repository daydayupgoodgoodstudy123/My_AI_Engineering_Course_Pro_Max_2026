"""Original interview practice for 05-nlp-foundations-to-advanced/11-machine-translation.

Local source: phases/05-nlp-foundations-to-advanced/11-machine-translation/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import json
from collections import Counter

def ngram_counts(tokens, n):
    if type(n) is not int or n <= 0:
        raise ValueError('n')
    return dict(Counter((json.dumps(tokens[i:i + n]) for i in range(len(tokens) - n + 1))))

def token_f1(reference, answer):
    if not reference or not answer:
        return 1 if not reference and (not answer) else 0
    overlap = sum((Counter(reference) & Counter(answer)).values())
    p = overlap / len(answer)
    r = overlap / len(reference)
    return 2 * p * r / (p + r) if p + r else 0
