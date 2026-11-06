"""Original interview practice for 20-recursive-self-improvement/10-self-modifying-agents-dgm-hgm-hyperagents.

Local source: phases/20-recursive-self-improvement/10-self-modifying-agents-dgm-hgm-hyperagents/code/main.py (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def select_ucb(means, visits, total, exploration):
    """means/visits must be same-length nonempty lists; visits are exact nonnegative ints; total exact int >=1, exploration>=0. Return first unvisited index if any; else maximize mean+c*sqrt(log(total)/visits), ties lower index. Invalid input raises ValueError."""
    raise NotImplementedError('TODO 1: select_ucb; see PROMPT.md')

def pareto_front(candidates):
    """Candidates have unique id strings, quality higher-is-better, cost lower-is-better. Return sorted ids not dominated by another candidate that is no worse in both and strictly better in at least one. Equal quality/cost entries both survive; empty input yields []."""
    raise NotImplementedError('TODO 2: pareto_front; see PROMPT.md')
