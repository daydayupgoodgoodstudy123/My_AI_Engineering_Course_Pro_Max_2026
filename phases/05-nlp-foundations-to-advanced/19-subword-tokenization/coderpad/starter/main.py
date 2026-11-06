"""Original interview practice for 05-nlp-foundations-to-advanced/19-subword-tokenization.

Local source: phases/05-nlp-foundations-to-advanced/19-subword-tokenization/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import json
from collections import Counter

def merge_pair(tokens, pair):
    """pair must contain exactly two strings. Scan tokens left to right, replacing each non-overlapping adjacent match with concatenation. Preserve unmatched tokens. Invalid pair raises ValueError; input lists do not mutate."""
    raise NotImplementedError('TODO 1: merge_pair; see PROMPT.md')

def ngram_counts(tokens, n):
    """n is exact positive int. Return a dict whose keys are JSON strings encoding each token window (json.dumps defaults) and whose values are counts. n>len(tokens) or empty tokens returns {}. Invalid n raises ValueError."""
    raise NotImplementedError('TODO 2: ngram_counts; see PROMPT.md')
