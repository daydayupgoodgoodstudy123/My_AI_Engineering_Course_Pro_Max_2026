"""Original interview practice for 10-llms-from-scratch/01-tokenizers.

Local source: phases/10-llms-from-scratch/01-tokenizers/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import re

def tokenize(text):
    return re.findall('[a-z0-9]+', text.casefold())

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
