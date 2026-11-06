"""Original interview practice for 17-infrastructure-and-production/15-batch-apis.

Local source: phases/17-infrastructure-and-production/15-batch-apis/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def make_batches(items, maximum):
    """items are {'id','tokens':exact positive int}; maximum exact positive int. Preserve input order, greedily pack consecutive items while sum tokens<=maximum. Oversized item raises ValueError rather than silently dropping it. Return list of lists of ids; empty input yields []."""
    raise NotImplementedError('TODO 1: make_batches; see PROMPT.md')

def budget_decisions(costs, limit):
    """Sequentially accept each nonnegative numeric cost if spent+cost<=limit, otherwise reject and keep spent unchanged. Return {'accepted':[bool per request],'spent':total}. Negative limit/cost raises ValueError. No rounding, billing API, or actual charge."""
    raise NotImplementedError('TODO 2: budget_decisions; see PROMPT.md')
