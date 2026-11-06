"""Original interview practice for 02-ml-fundamentals/08-feature-engineering.

Local source: phases/02-ml-fundamentals/08-feature-engineering/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math
from collections import Counter

def standardize(train, values):
    """Compute mean and population standard deviation from nonempty train, then transform values. If training variance is zero use scale=1. Return {'mean','scale','values'}. Never fit on values; empty train raises ValueError."""
    raise NotImplementedError('TODO 1: standardize; see PROMPT.md')

def bag_of_words(tokens, vocabulary):
    """Return counts aligned to an ordered vocabulary of unique strings; ignore unknown tokens. Duplicate vocabulary entries raise ValueError. Empty vocabulary returns []. No normalization."""
    raise NotImplementedError('TODO 2: bag_of_words; see PROMPT.md')
