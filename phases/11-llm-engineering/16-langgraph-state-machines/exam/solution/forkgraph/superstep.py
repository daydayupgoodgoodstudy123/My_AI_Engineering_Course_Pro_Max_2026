"""Send-shaped local worker barrier over one common pre-step state."""
import copy
from .contracts import StepResult,validate_delta
from .forks import merge_single
def run_superstep(state,reducers,workers,completion_order):
    """Execute supplied local workers against independent copies of the same pre-state.

    completion_order names each declared worker exactly once and simulates arrival
    order; no actual threads or SDK concurrency are claimed. Collect all deltas
    before reducing; merge in workers declaration order, independent of completion.
    More than one writer to an overwrite field rejects even for equal values.
    Input state remains unchanged, and no worker sees any sibling partial result.
    Repaired P1 merge_single is the given single-update dependency, not this barrier.
    Return final state, declaration-ordered (worker_name,delta) evidence and actual
    completion order. Empty workers preserve state. No checkpoint is committed here.
    """
    names=tuple(worker.name for worker in workers)
    if len(set(names))!=len(names) or len(completion_order)!=len(names) or set(completion_order)!=set(names):raise ValueError("worker order")
    by_name={worker.name:worker for worker in workers};outputs={}
    for name in completion_order:
        delta=by_name[name].run(copy.deepcopy(state));validate_delta(delta,reducers);outputs[name]=copy.deepcopy(delta)
    writes={}
    for name in names:
        for key in outputs[name]:writes[key]=writes.get(key,0)+1
    if any(count>1 and reducers[key]=="overwrite" for key,count in writes.items()):raise ValueError("parallel overwrite conflict")
    merged=copy.deepcopy(state)
    for name in names:merge_single(merged,outputs[name],reducers)
    return StepResult(merged,tuple((name,outputs[name]) for name in names),tuple(completion_order))
