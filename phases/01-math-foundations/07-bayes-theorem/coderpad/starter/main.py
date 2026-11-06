"""Original interview practice for 01-math-foundations/07-bayes-theorem.

Local source: phases/01-math-foundations/07-bayes-theorem/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def bayes(prior, likelihood_positive, likelihood_negative):
    """For three probabilities in [0,1], return P(H|E)=prior*likelihood_positive/(prior*likelihood_positive+(1-prior)*likelihood_negative). Out-of-range values or zero evidence probability raise ValueError."""
    raise NotImplementedError('TODO 1: bayes; see PROMPT.md')

def classification(expected, predicted):
    """Require equal-length exact-bool lists. Return tp,fp,fn,tn,precision,recall,f1. A ratio with zero denominator is 0.0. Empty lists are valid; invalid labels raise ValueError."""
    raise NotImplementedError('TODO 2: classification; see PROMPT.md')
