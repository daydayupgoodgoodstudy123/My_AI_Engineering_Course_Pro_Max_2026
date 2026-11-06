"""Original interview practice for 11-llm-engineering/16-langgraph-state-machines.

Local source: phases/11-llm-engineering/16-langgraph-state-machines/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def transition(state, target):
    """Allowed edges: queued->running/canceled; running->waiting/completed/failed/canceled; waiting->running/canceled. Return target if allowed, otherwise ValueError. Terminal states cannot transition, including to themselves."""
    raise NotImplementedError('TODO 1: transition; see PROMPT.md')

def topological_order(dependencies):
    """dependencies maps node string to prerequisite-name list. Include names appearing only as prerequisites. Return lexicographically smallest available node at each step. Cycles raise ValueError. Duplicate dependencies count once; empty graph returns []."""
    raise NotImplementedError('TODO 2: topological_order; see PROMPT.md')
