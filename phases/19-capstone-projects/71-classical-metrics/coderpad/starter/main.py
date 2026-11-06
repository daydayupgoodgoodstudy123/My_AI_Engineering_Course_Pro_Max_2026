"""Original interview practice for 19-capstone-projects/71-classical-metrics.

Local source: phases/19-capstone-projects/71-classical-metrics/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import json
from collections import Counter

def token_f1(reference, answer):
    """Inputs are token lists; count overlap as multiset intersection. Both empty ->1; exactly one empty ->0. Otherwise return harmonic mean of overlap/len(answer) and overlap/len(reference)."""
    raise NotImplementedError('TODO 1: token_f1; see PROMPT.md')

def ngram_counts(tokens, n):
    """n is exact positive int. Return a dict whose keys are JSON strings encoding each token window (json.dumps defaults) and whose values are counts. n>len(tokens) or empty tokens returns {}. Invalid n raises ValueError."""
    raise NotImplementedError('TODO 2: ngram_counts; see PROMPT.md')
