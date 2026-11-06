"""Original interview practice for 02-ml-fundamentals/14-naive-bayes.

Local source: phases/02-ml-fundamentals/14-naive-bayes/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
from collections import Counter

def bag_of_words(tokens, vocabulary):
    if len(set(vocabulary)) != len(vocabulary):
        raise ValueError('duplicate vocabulary')
    counts = Counter(tokens)
    return [counts[t] for t in vocabulary]

def bayes(prior, likelihood_positive, likelihood_negative):
    if any((not 0 <= x <= 1 for x in (prior, likelihood_positive, likelihood_negative))):
        raise ValueError('probability')
    den = prior * likelihood_positive + (1 - prior) * likelihood_negative
    if den == 0:
        raise ValueError('impossible evidence')
    return prior * likelihood_positive / den
