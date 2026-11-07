"""Candidate actual numeric iteration/inference/learning domain field projection."""
from .wire_support import observation_kind,learning_status
def observation_fields(event):
    """Project each typed event's own actual fields, retaining best versus mean and original delayed learning attribution."""
    kind=observation_kind(event)
    if kind=='iteration':
        r=event.report
        return dict(kind=kind,run=event.run_uid,iteration=r.iteration,best_fitness=r.best.fitness,mean_fitness=r.population_mean,best=list(r.best.coordinates),current_scores=list(r.current_scores))
    if kind=='route':
        c=event.choice
        return dict(kind=kind,task=c.task_uid,task_type=c.task_type,agent=c.agent_uid,draw=c.draw,total=c.total)
    d=event.decision
    return dict(kind=kind,outcome=d.outcome_uid,allocation=d.allocation_uid,task=d.task_uid,task_type=d.task_type,agent=d.agent_uid,arrival=d.arrival,epoch=d.epoch,quality=d.quality,status=learning_status(d),amount=d.amount,reason=d.reason)
