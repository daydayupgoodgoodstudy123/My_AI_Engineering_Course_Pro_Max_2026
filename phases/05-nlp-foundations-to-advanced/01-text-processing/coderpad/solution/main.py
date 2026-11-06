"""Original interview practice for 05-nlp-foundations-to-advanced/01-text-processing.

Local source: phases/05-nlp-foundations-to-advanced/01-text-processing/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import re
import json
from collections import Counter

def tokenize(text):
    return re.findall('[a-z0-9]+', text.casefold())

def ngram_counts(tokens, n):
    if type(n) is not int or n <= 0:
        raise ValueError('n')
    return dict(Counter((json.dumps(tokens[i:i + n]) for i in range(len(tokens) - n + 1))))
