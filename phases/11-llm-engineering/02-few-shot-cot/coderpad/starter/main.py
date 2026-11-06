"""Original interview practice for 11-llm-engineering/02-few-shot-cot.

Local source: phases/11-llm-engineering/02-few-shot-cot/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
from collections import Counter

def select_context(items, budget):
    """items contain id(str), tokens(exact nonnegative int), score(number). Sort descending score with lexicographic id ties, then greedily accept each item that fits remaining exact nonnegative integer budget; skip oversize items and continue. Return selected ids in that order. Invalid costs/budget raise ValueError."""
    raise NotImplementedError('TODO 1: select_context; see PROMPT.md')

def token_f1(reference, answer):
    """Inputs are token lists; count overlap as multiset intersection. Both empty ->1; exactly one empty ->0. Otherwise return harmonic mean of overlap/len(answer) and overlap/len(reference)."""
    raise NotImplementedError('TODO 2: token_f1; see PROMPT.md')
