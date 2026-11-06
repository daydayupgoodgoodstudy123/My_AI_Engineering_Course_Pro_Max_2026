"""Original interview practice for 02-ml-fundamentals/11-ensemble-methods.

Local source: phases/02-ml-fundamentals/11-ensemble-methods/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
from collections import Counter

def majority_votes(predictions):
    """Input is model-by-example label matrix of strings. Return one majority label per example; ties choose lexicographically smallest label. Empty model list returns []; ragged rows raise ValueError."""
    raise NotImplementedError('TODO 1: majority_votes; see PROMPT.md')

def classification(expected, predicted):
    """Require equal-length exact-bool lists. Return tp,fp,fn,tn,precision,recall,f1. A ratio with zero denominator is 0.0. Empty lists are valid; invalid labels raise ValueError."""
    raise NotImplementedError('TODO 2: classification; see PROMPT.md')
