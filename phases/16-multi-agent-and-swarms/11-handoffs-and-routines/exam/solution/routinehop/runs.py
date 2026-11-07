"""Compose independent caller-owned runs using the corrected flat batch interpreter."""
from .models import BatchStep,OwnBatchAudit,ChildAudit,RunAudit
def audit_run(node,catalog,batch_runner):
    """Continue active state only across this run's batches; independent child runs own their state.

    Preserve declared step order and own receipts. A child final routine and history
    never replace the caller's continuation, including when a child is the final step.
    """
    initial=catalog.agent(node.initial);active=initial;history=[];steps=[]
    for step in node.steps:
        if isinstance(step,BatchStep):
            report=batch_runner(active,step.calls,catalog)
            steps.append(OwnBatchAudit(step.step_id,active.name,report.active.name,report.receipts))
            history.extend(report.receipts);active=report.active
        else:
            child=audit_run(step.run,catalog,batch_runner)
            steps.append(ChildAudit(step.step_id,child))
    return RunAudit(node.run_id,initial.name,active.name,tuple(history),tuple(steps))
