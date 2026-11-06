"""Original interview practice for 05-nlp-foundations-to-advanced/02-bag-of-words-tfidf.

Local source: phases/05-nlp-foundations-to-advanced/02-bag-of-words-tfidf/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math
from collections import Counter

def bag_of_words(tokens, vocabulary):
    if len(set(vocabulary)) != len(vocabulary):
        raise ValueError('duplicate vocabulary')
    counts = Counter(tokens)
    return [counts[t] for t in vocabulary]

def cosine(a, b):
    if len(a) != len(b):
        raise ValueError('shape')
    den = math.sqrt(sum((x * x for x in a)) * sum((y * y for y in b)))
    return sum((x * y for x, y in zip(a, b))) / den if den else 0
