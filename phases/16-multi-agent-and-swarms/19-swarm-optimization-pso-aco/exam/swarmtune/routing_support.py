"""Complete finite numeric intake, stable immutable inference snapshot and record constructors; no route/decay/gate policy."""
import math
from .models import RouteTable,RouteRow,LearningDecision
def stable_snapshot(table):return RouteTable(tuple(RouteRow(r.task_type,tuple(r.weights))for r in table.rows),tuple(table.applied_epochs))
def requested_row(table,task_type):
    rows=[r for r in table.rows if r.task_type==task_type]
    if len(rows)!=1:raise ValueError('one declared task row required')
    row=rows[0]
    if not row.weights or len(dict(row.weights))!=len(row.weights)or any(not math.isfinite(w)or w<0 for _,w in row.weights)or not math.isfinite(sum(w for _,w in row.weights))or sum(w for _,w in row.weights)<=0:raise ValueError('finite nonnegative positive-total weights required')
    return row
def allocation_for(ledger,uid):return next((a for a in ledger if a.uid==uid),None)
def decision_for(outcome,allocation,accepted,amount,reason):
    return LearningDecision(outcome.uid,outcome.allocation_uid,allocation.task_uid if allocation else None,allocation.task_type if allocation else None,allocation.agent_uid if allocation else None,outcome.quality,outcome.arrival,outcome.epoch,accepted,amount,reason)

def decay_domain(table,epoch,rho,floor):
    """Complete finite numeric/epoch intake only; no decay or epoch replay decision."""
    if len(set(table.applied_epochs))!=len(table.applied_epochs)or any(type(e)is not int or e<0 for e in table.applied_epochs):raise ValueError('unique nonnegative declared epochs required')
    if type(epoch)is not int or epoch<0 or not math.isfinite(rho)or not 0<=rho<=1 or not math.isfinite(floor)or floor<0:raise ValueError('declared finite decay domain required')
    if len({r.task_type for r in table.rows})!=len(table.rows)or any(len(dict(r.weights))!=len(r.weights)or any(not math.isfinite(w)or w<0 for _,w in r.weights)for r in table.rows):raise ValueError('unique finite routing declarations required')
def feedback_domain(table,ledger,outcome,policy):
    """Validate declared finite replay inputs without deciding acceptance or selecting an allocation."""
    decay_domain(table,outcome.epoch,0.,0.)
    if len({a.uid for a in ledger})!=len(ledger):raise ValueError('unique allocation ledger required')
    if not math.isfinite(outcome.quality)or not 0<=outcome.quality<=1 or not math.isfinite(policy.threshold)or not 0<=policy.threshold<=1 or not math.isfinite(policy.reinforce)or policy.reinforce<0:raise ValueError('finite normalized quality and policy required')
    amount=policy.reinforce*outcome.quality
    if not math.isfinite(amount)or any(not math.isfinite(w+amount)for r in table.rows for _,w in r.weights):raise ValueError('conservative representable learning update required')
