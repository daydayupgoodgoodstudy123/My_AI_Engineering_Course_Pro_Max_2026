"""Given complete ownership boundary for the deterministic local Send harness.

The candidate kernel receives private state and wrapped workers. This module
owns caller-state, worker-input, returned-delta and published-result containers.
It does not implement a barrier, worker multiplicity, reducer order or conflicts.
These are local simulator guarantees, not claims about a framework SDK.
"""
import copy
from .contracts import Worker,StepResult,validate_delta
def caller_snapshot(state):
    """Own the initial working state before calling candidate code."""
    return copy.deepcopy(state)
def worker_snapshot(state):
    """Own every input passed to one local worker invocation."""
    return copy.deepcopy(state)
def protected_worker(worker,reducers):
    """Retain a callable while owning its input and returned partial update."""
    def invoke(state):
        delta=worker.run(worker_snapshot(state))
        validate_delta(delta,reducers)
        return copy.deepcopy(delta)
    return Worker(worker.name,invoke)
def run_owned(state,reducers,workers,completion_order,kernel):
    """Invoke an algorithm kernel with owned containers, then publish owned results.

    A worker receives the state chosen by the kernel at its actual invocation.
    This boundary clones containers; it does not undo premature state reductions.
    The kernel must therefore retain the common pre-state until all workers finish.
    Published final state and each evidence delta have separate ownership, even
    if a kernel returns containers that internally alias one another.
    """
    owned=caller_snapshot(state);local_reducers=dict(reducers)
    wrapped=tuple(protected_worker(worker,local_reducers) for worker in workers)
    result=kernel(owned,local_reducers,wrapped,tuple(completion_order))
    if not isinstance(result,StepResult):raise ValueError("step result")
    validate_delta(result.state,local_reducers)
    updates=[]
    for name,delta in result.worker_updates:
        validate_delta(delta,local_reducers);updates.append((name,copy.deepcopy(delta)))
    return StepResult(copy.deepcopy(result.state),tuple(updates),tuple(result.completion_order))
