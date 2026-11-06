"""Original interview practice for 02-ml-fundamentals/04-decision-trees.

Local source: phases/02-ml-fundamentals/04-decision-trees/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math
from collections import Counter

def gini(labels):
    """Return 1-sum(class_fraction^2) for hashable labels. Empty labels returns 0. Labels may be strings or integers."""
    raise NotImplementedError('TODO 1: gini; see PROMPT.md')

def entropy(probabilities):
    """Return Shannon entropy in bits. Require a nonempty list of numeric probabilities in [0,1] summing to 1 within 1e-9, else ValueError. Define 0*log2(0)=0."""
    raise NotImplementedError('TODO 2: entropy; see PROMPT.md')
