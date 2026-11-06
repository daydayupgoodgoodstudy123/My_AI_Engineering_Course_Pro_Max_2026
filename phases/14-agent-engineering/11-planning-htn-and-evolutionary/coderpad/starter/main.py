"""Original interview practice for 14-agent-engineering/11-planning-htn-and-evolutionary.

Local source: phases/14-agent-engineering/11-planning-htn-and-evolutionary/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def topological_order(dependencies):
    """dependencies maps node string to prerequisite-name list. Include names appearing only as prerequisites. Return lexicographically smallest available node at each step. Cycles raise ValueError. Duplicate dependencies count once; empty graph returns []."""
    raise NotImplementedError('TODO 1: topological_order; see PROMPT.md')

def pareto_front(candidates):
    """Candidates have unique id strings, quality higher-is-better, cost lower-is-better. Return sorted ids not dominated by another candidate that is no worse in both and strictly better in at least one. Equal quality/cost entries both survive; empty input yields []."""
    raise NotImplementedError('TODO 2: pareto_front; see PROMPT.md')
