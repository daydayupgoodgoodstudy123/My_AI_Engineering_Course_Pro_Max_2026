"""Specialist pull with age-based priority at the actual claim instant."""
def eligible_ready_tasks(now,ready,worker):
    """Return only ready tasks whose topic this worker subscribes to; preserve input order."""
    raise NotImplementedError

def effective_priority(task,now,aging_interval):
    """Base priority plus full enqueue-age intervals; future work cannot be pulled."""
    raise NotImplementedError

def claim_free_workers(now,ready,free,task_sequence,aging_interval):
    """In declared worker order, claim the best eligible remaining task once.

    Higher effective priority wins; equal scores use original task sequence.
    Running tasks are absent from ready/free and are never preempted.
    """
    raise NotImplementedError
