"""Original interview practice for 02-ml-fundamentals/12-hyperparameter-tuning.

Local source: phases/02-ml-fundamentals/12-hyperparameter-tuning/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import itertools

def grid(parameters, limit):
    """Enumerate Cartesian products with parameter keys sorted lexicographically and option order preserved. Return at most limit dicts; limit is exact nonnegative int. Empty parameter dict produces [{}] if limit>0. Any empty option list produces []. Invalid limit raises ValueError."""
    raise NotImplementedError('TODO 1: grid; see PROMPT.md')

def top_k(scores, k):
    """Return the indices of k largest scores, descending score with lower original index ties. k exact int in [0,len(scores)], else ValueError; k=0 returns []."""
    raise NotImplementedError('TODO 2: top_k; see PROMPT.md')
