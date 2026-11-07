"""Three candidate algorithms: requested-row roulette, explicit decay and original-allocation verified feedback."""
from .models import RouteChoice,RouteRow,RouteTable,LearningResult
from .routing_support import requested_row,allocation_for,decision_for,decay_domain,feedback_domain
def choose_task_route(snapshot,task_uid,task_type,rng):
    """Choose in the requested immutable task row using one real draw and declared half-open cumulative intervals."""
    raise NotImplementedError
def apply_route_decay(table,epoch,rho,floor=0.):
    """Apply the declared complete-table decay once per explicit epoch while preserving row order and declared floor."""
    raise NotImplementedError
def apply_verified_feedback(table,ledger,outcome,policy):
    """Bind delayed outcome to its original task/agent and emit a complete accepted or rejected learning decision."""
    raise NotImplementedError
