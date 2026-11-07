"""Completion identity and producer termination for a FIFO replay."""
from .support import increment_worker_histogram

def record_completion(ledger,completion):
    """Keep the task result and actual worker separately; update the supplied count."""
    ledger.by_task[completion.task_id]=completion
    ledger.completions.append(completion)
    increment_worker_histogram(ledger,completion)

def producer_finished(ready,running,future_arrivals):
    """Return true only after pending arrivals and all claimed/ready work are drained."""
    return not ready and not running and not future_arrivals
