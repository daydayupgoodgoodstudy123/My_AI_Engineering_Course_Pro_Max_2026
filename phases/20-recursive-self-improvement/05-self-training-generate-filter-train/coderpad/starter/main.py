"""Original interview practice for 20-recursive-self-improvement/05-self-training-generate-filter-train.

Local source: phases/20-recursive-self-improvement/05-self-training-generate-filter-train/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
from collections import Counter

def classification(expected, predicted):
    """Require equal-length exact-bool lists. Return tp,fp,fn,tn,precision,recall,f1. A ratio with zero denominator is 0.0. Empty lists are valid; invalid labels raise ValueError."""
    raise NotImplementedError('TODO 1: classification; see PROMPT.md')

def class_weights(labels):
    """Return string label -> n/(number_of_classes*class_count). Empty labels returns {}. Labels are provided strings; do not alter input order or labels."""
    raise NotImplementedError('TODO 2: class_weights; see PROMPT.md')
