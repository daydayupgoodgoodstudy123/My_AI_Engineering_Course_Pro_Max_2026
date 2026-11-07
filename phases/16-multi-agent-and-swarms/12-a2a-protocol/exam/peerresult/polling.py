"""Batch observation with independent logical deadlines; no sleeps or HTTP."""
from .models import TaskEnvelope,BatchResult
from .primitives import make_poll_url,task_id_from_route,classify_terminal
def poll_pending(requests,transport):
    """Read only unfinished tasks, retaining each first terminal result in request order.

    Logical ticks start at zero. A task may complete exactly at its deadline;
    an otherwise unfinished task times out at that tick. Request IDs are unique.
    """
    pending={r.task_id:r for r in requests};results={};tick=0
    while pending:
        for request in requests:
            document=transport.get(make_poll_url(request.endpoint,request.task_id,request.query),tick,task_id_from_route)
            if request.task_id in results:continue
            envelope=classify_terminal(document,tick)
            if envelope is None and tick>=request.deadline:envelope=TaskEnvelope(request.task_id,'timeout',None,tick)
            if envelope is not None:
                results[request.task_id]=envelope
                pending.pop(request.task_id)
        tick+=1
    return BatchResult(tuple(results[r.task_id]for r in requests))
