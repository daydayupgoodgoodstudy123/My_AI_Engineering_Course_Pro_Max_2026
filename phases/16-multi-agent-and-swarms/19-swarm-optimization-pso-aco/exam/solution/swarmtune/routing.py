"""Three candidate algorithms: requested-row roulette, explicit decay and original-allocation verified feedback."""
from .models import RouteChoice,RouteRow,RouteTable,LearningResult
from .routing_support import requested_row,allocation_for,decision_for,decay_domain,feedback_domain
def choose_task_route(snapshot,task_uid,task_type,rng):
    """Choose in the requested immutable task row using one real draw and declared half-open cumulative intervals."""
    row=requested_row(snapshot,task_type);total=sum(w for _,w in row.weights);draw=rng.random()*total;upto=0.;chosen=None
    for agent,weight in row.weights:
        upto+=weight
        if draw<upto:chosen=agent;break
    if chosen is None:chosen=next(agent for agent,weight in reversed(row.weights)if weight>0)
    return RouteChoice(task_uid,task_type,chosen,draw,total,snapshot)
def apply_route_decay(table,epoch,rho,floor=0.):
    """Apply the declared complete-table decay once per explicit epoch while preserving row order and declared floor."""
    decay_domain(table,epoch,rho,floor)
    if epoch in table.applied_epochs:return table
    return RouteTable(tuple(RouteRow(r.task_type,tuple((a,max(floor,w*(1-rho)))for a,w in r.weights))for r in table.rows),table.applied_epochs+(epoch,))
def apply_verified_feedback(table,ledger,outcome,policy):
    """Bind delayed outcome to its original task/agent and emit a complete accepted or rejected learning decision."""
    feedback_domain(table,ledger,outcome,policy);allocation=allocation_for(ledger,outcome.allocation_uid);reason='accepted'
    if allocation is None:reason='unknown-allocation'
    elif not any(r.task_type==allocation.task_type and allocation.agent_uid in dict(r.weights)for r in table.rows):reason='unknown-route'
    elif not outcome.verified:reason='unverified'
    elif not outcome.success:reason='failed'
    elif outcome.quality<policy.threshold:reason='below-quality'
    accepted=reason=='accepted';amount=policy.reinforce*outcome.quality if accepted else 0.
    if accepted:table=RouteTable(tuple(RouteRow(r.task_type,tuple((a,w+amount if r.task_type==allocation.task_type and a==allocation.agent_uid else w)for a,w in r.weights))for r in table.rows),table.applied_epochs)
    return LearningResult(table,decision_for(outcome,allocation,accepted,amount,reason))
