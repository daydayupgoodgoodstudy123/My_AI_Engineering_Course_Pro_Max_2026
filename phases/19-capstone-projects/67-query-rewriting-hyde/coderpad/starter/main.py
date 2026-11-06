"""Original interview practice for 19-capstone-projects/67-query-rewriting-hyde.

Local source: phases/19-capstone-projects/67-query-rewriting-hyde/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
from collections import Counter

def bag_of_words(tokens, vocabulary):
    """Return counts aligned to an ordered vocabulary of unique strings; ignore unknown tokens. Duplicate vocabulary entries raise ValueError. Empty vocabulary returns []. No normalization."""
    raise NotImplementedError('TODO 1: bag_of_words; see PROMPT.md')

def rrf(rankings, constant=60):
    """For each ranking, score each id once at its FIRST 1-based rank using 1/(constant+rank). Sum across lists. Return ids sorted by descending total score, then lexicographic id. constant>=0 else ValueError; empty rankings yields []."""
    raise NotImplementedError('TODO 2: rrf; see PROMPT.md')
