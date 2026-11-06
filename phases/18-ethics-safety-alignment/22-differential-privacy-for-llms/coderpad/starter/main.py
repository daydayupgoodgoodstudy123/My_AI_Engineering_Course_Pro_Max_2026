"""Original interview practice for 18-ethics-safety-alignment/22-differential-privacy-for-llms.

Local source: phases/18-ethics-safety-alignment/22-differential-privacy-for-llms/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def privacy_budget(epsilons, deltas, max_epsilon, max_delta):
    """Require equal-length nonnegative epsilons/deltas and nonnegative maxima; otherwise ValueError. Basic sequential composition returns {'epsilon':sum eps,'delta':sum deltas,'within_budget':both totals<=maxima}. No advanced accountant or real privacy guarantee is implemented."""
    raise NotImplementedError('TODO 1: privacy_budget; see PROMPT.md')

def budget_decisions(costs, limit):
    """Sequentially accept each nonnegative numeric cost if spent+cost<=limit, otherwise reject and keep spent unchanged. Return {'accepted':[bool per request],'spent':total}. Negative limit/cost raises ValueError. No rounding, billing API, or actual charge."""
    raise NotImplementedError('TODO 2: budget_decisions; see PROMPT.md')
