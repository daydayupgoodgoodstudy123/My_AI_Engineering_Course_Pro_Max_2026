"""Original interview practice for 05-nlp-foundations-to-advanced/15-topic-modeling.

Local source: phases/05-nlp-foundations-to-advanced/15-topic-modeling/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math
from collections import Counter

def bag_of_words(tokens, vocabulary):
    """Return counts aligned to an ordered vocabulary of unique strings; ignore unknown tokens. Duplicate vocabulary entries raise ValueError. Empty vocabulary returns []. No normalization."""
    raise NotImplementedError('TODO 1: bag_of_words; see PROMPT.md')

def entropy(probabilities):
    """Return Shannon entropy in bits. Require a nonempty list of numeric probabilities in [0,1] summing to 1 within 1e-9, else ValueError. Define 0*log2(0)=0."""
    raise NotImplementedError('TODO 2: entropy; see PROMPT.md')
