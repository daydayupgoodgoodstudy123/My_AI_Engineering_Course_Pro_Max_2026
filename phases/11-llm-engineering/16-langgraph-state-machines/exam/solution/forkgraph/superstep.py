"""Send-shaped local barrier and declaration-order reducer algorithm."""
from .contracts import StepResult
from .forks import merge_single
from .superstep_runtime import run_owned
def run_superstep(state,reducers,workers,completion_order):
    """Given public ownership boundary; assemble_superstep implements the algorithm."""
    return run_owned(state,reducers,workers,completion_order,assemble_superstep)
def assemble_superstep(state,reducers,workers,completion_order):
    """Collect one update per declared worker before reducing any field.

    Inputs are an owned working state, reducer metadata, and workers whose input
    and returned deltas are fully owned by the Given runtime. Preserve that common
    pre-state until every completion has been collected. Completion order names
    every declared worker exactly once and simulates arrival, not actual threads.
    After collection reject multiple overwrite writers, even equal values, then
    merge in worker declaration order using repaired P1 merge_single. Return a
    StepResult with full final state, declaration-ordered updates and actual
    completion order; empty workers preserve state. No checkpoint is committed.
    All recursive ownership and final publication copying are Given dependencies.
    """
    names=tuple(worker.name for worker in workers)
    if len(set(names))!=len(names) or len(completion_order)!=len(names) or set(completion_order)!=set(names):raise ValueError("worker order")
    by_name={worker.name:worker for worker in workers};outputs={}
    for name in completion_order:
        outputs[name]=by_name[name].run(state)
    writes={}
    for name in names:
        for key in outputs[name]:writes[key]=writes.get(key,0)+1
    if any(count>1 and reducers[key]=="overwrite" for key,count in writes.items()):raise ValueError("parallel overwrite conflict")
    merged=state
    for name in names:merge_single(merged,outputs[name],reducers)
    return StepResult(merged,tuple((name,outputs[name]) for name in names),tuple(completion_order))
