"""Original interview practice for 02-ml-fundamentals/14-naive-bayes.

Local source: phases/02-ml-fundamentals/14-naive-bayes/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
from collections import Counter

def bag_of_words(tokens, vocabulary):
    """Return counts aligned to an ordered vocabulary of unique strings; ignore unknown tokens. Duplicate vocabulary entries raise ValueError. Empty vocabulary returns []. No normalization."""
    raise NotImplementedError('TODO 1: bag_of_words; see PROMPT.md')

def bayes(prior, likelihood_positive, likelihood_negative):
    """For three probabilities in [0,1], return P(H|E)=prior*likelihood_positive/(prior*likelihood_positive+(1-prior)*likelihood_negative). Out-of-range values or zero evidence probability raise ValueError."""
    raise NotImplementedError('TODO 2: bayes; see PROMPT.md')
