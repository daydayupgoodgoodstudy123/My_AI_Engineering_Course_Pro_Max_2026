"""Original interview practice for 18-ethics-safety-alignment/13-many-shot-jailbreaking.

Local source: phases/18-ethics-safety-alignment/13-many-shot-jailbreaking/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def select_context(items, budget):
    """items contain id(str), tokens(exact nonnegative int), score(number). Sort descending score with lexicographic id ties, then greedily accept each item that fits remaining exact nonnegative integer budget; skip oversize items and continue. Return selected ids in that order. Invalid costs/budget raise ValueError."""
    raise NotImplementedError('TODO 1: select_context; see PROMPT.md')

def budget_decisions(costs, limit):
    """Sequentially accept each nonnegative numeric cost if spent+cost<=limit, otherwise reject and keep spent unchanged. Return {'accepted':[bool per request],'spent':total}. Negative limit/cost raises ValueError. No rounding, billing API, or actual charge."""
    raise NotImplementedError('TODO 2: budget_decisions; see PROMPT.md')
