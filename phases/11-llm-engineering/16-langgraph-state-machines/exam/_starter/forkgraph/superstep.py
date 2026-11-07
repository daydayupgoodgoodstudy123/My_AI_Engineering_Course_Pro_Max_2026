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
    raise NotImplementedError
