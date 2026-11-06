"""Original interview practice for 18-ethics-safety-alignment/20-bias-representational-harm.

Local source: phases/18-ethics-safety-alignment/20-bias-representational-harm/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
from collections import Counter

def selection_gap(groups, selected):
    """Equal-length nonempty lists; groups are strings and selected exact booleans. Return {'rates':group->selected_count/group_count,'gap':max(rate)-min(rate)}. Invalid length/labels raises ValueError. This is descriptive demographic-parity evidence, not a complete fairness judgment."""
    raise NotImplementedError('TODO 1: selection_gap; see PROMPT.md')

def classification(expected, predicted):
    """Require equal-length exact-bool lists. Return tp,fp,fn,tn,precision,recall,f1. A ratio with zero denominator is 0.0. Empty lists are valid; invalid labels raise ValueError."""
    raise NotImplementedError('TODO 2: classification; see PROMPT.md')
