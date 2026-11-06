"""Original interview practice for 19-capstone-projects/56-iteration-scheduler.

Local source: phases/19-capstone-projects/56-iteration-scheduler/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def select_ucb(means, visits, total, exploration):
    """means/visits must be same-length nonempty lists; visits are exact nonnegative ints; total exact int >=1, exploration>=0. Return first unvisited index if any; else maximize mean+c*sqrt(log(total)/visits), ties lower index. Invalid input raises ValueError."""
    raise NotImplementedError('TODO 1: select_ucb; see PROMPT.md')

def budget_decisions(costs, limit):
    """Sequentially accept each nonnegative numeric cost if spent+cost<=limit, otherwise reject and keep spent unchanged. Return {'accepted':[bool per request],'spent':total}. Negative limit/cost raises ValueError. No rounding, billing API, or actual charge."""
    raise NotImplementedError('TODO 2: budget_decisions; see PROMPT.md')
