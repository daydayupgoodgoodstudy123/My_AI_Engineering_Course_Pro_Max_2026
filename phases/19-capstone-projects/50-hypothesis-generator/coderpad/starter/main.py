"""Original interview practice for 19-capstone-projects/50-hypothesis-generator.

Local source: phases/19-capstone-projects/50-hypothesis-generator/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def select_context(items, budget):
    """items contain id(str), tokens(exact nonnegative int), score(number). Sort descending score with lexicographic id ties, then greedily accept each item that fits remaining exact nonnegative integer budget; skip oversize items and continue. Return selected ids in that order. Invalid costs/budget raise ValueError."""
    raise NotImplementedError('TODO 1: select_context; see PROMPT.md')

def pareto_front(candidates):
    """Candidates have unique id strings, quality higher-is-better, cost lower-is-better. Return sorted ids not dominated by another candidate that is no worse in both and strictly better in at least one. Equal quality/cost entries both survive; empty input yields []."""
    raise NotImplementedError('TODO 2: pareto_front; see PROMPT.md')
