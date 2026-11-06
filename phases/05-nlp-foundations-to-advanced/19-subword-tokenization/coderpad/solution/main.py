"""Original interview practice for 05-nlp-foundations-to-advanced/19-subword-tokenization.

Local source: phases/05-nlp-foundations-to-advanced/19-subword-tokenization/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import json
from collections import Counter

def merge_pair(tokens, pair):
    if len(pair) != 2 or any((not isinstance(x, str) for x in pair)):
        raise ValueError('pair')
    result = []
    i = 0
    while i < len(tokens):
        if tokens[i:i + 2] == list(pair):
            result.append(pair[0] + pair[1])
            i += 2
        else:
            result.append(tokens[i])
            i += 1
    return result

def ngram_counts(tokens, n):
    if type(n) is not int or n <= 0:
        raise ValueError('n')
    return dict(Counter((json.dumps(tokens[i:i + n]) for i in range(len(tokens) - n + 1))))
