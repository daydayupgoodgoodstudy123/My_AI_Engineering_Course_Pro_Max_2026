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
    raise NotImplementedError('Part 3: superstep barrier, order and writer conflicts')
