"""Original interview practice for 14-agent-engineering/28-orchestration-patterns.

Local source: phases/14-agent-engineering/28-orchestration-patterns/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def topological_order(dependencies):
    """dependencies maps node string to prerequisite-name list. Include names appearing only as prerequisites. Return lexicographically smallest available node at each step. Cycles raise ValueError. Duplicate dependencies count once; empty graph returns []."""
    raise NotImplementedError('TODO 1: topological_order; see PROMPT.md')

def schedule_jobs(jobs, capacity):
    """Jobs have unique id(str), priority(number), created(number), status. Select only queued jobs, sorted priority descending, created ascending, id ascending. Return at most capacity ids. capacity exact nonnegative int; duplicate ids or invalid capacity raises ValueError."""
    raise NotImplementedError('TODO 2: schedule_jobs; see PROMPT.md')
