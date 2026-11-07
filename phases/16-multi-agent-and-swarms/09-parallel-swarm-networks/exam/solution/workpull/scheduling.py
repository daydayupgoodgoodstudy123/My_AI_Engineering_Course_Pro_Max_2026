"""Specialist pull with age-based priority at the actual claim instant."""
def eligible_ready_tasks(now,ready,worker):
    """Return only ready tasks whose topic this worker subscribes to; preserve input order."""
    return tuple(t for t in ready if t.arrival_us<=now and t.topic in worker.topics)

def effective_priority(task,now,aging_interval):
    """Base priority plus full enqueue-age intervals; future work cannot be pulled."""
    if now<task.arrival_us:raise ValueError('task not arrived')
    return task.priority+(now-task.arrival_us)//aging_interval

def claim_free_workers(now,ready,free,task_sequence,aging_interval):
    """In declared worker order, claim the best eligible remaining task once.

    Higher effective priority wins; equal scores use original task sequence.
    Running tasks are absent from ready/free and are never preempted.
    """
    remaining=list(ready);claims=[]
    for worker in free:
        eligible=eligible_ready_tasks(now,remaining,worker)
        if not eligible:continue
        task=min(eligible,key=lambda t:(-effective_priority(t,now,aging_interval),task_sequence[t.task_id]))
        claims.append((worker,task));remaining.remove(task)
    return tuple(claims)
