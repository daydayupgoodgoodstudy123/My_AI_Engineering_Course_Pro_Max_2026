"""Complete routine lookup and finite nested caller-tree intake; no continuation solver."""
from .models import RunNode,BatchStep,ChildRun
from .support import RoutineCatalog
class RunCatalog(RoutineCatalog):
    def validate_run(self,node):
        seen=set();stack=set()
        def visit(run):
            if not isinstance(run,RunNode)or id(run)in stack or run.run_id in seen:raise ValueError('finite caller tree with globally unique run ids')
            self.agent(run.initial);seen.add(run.run_id);stack.add(id(run))
            if any(not isinstance(step,(BatchStep,ChildRun))for step in run.steps):raise ValueError('typed caller step')
            if len({step.step_id for step in run.steps})!=len(run.steps):raise ValueError('unique step ids in each run')
            for step in run.steps:
                if isinstance(step,ChildRun):visit(step.run)
                elif not isinstance(step,BatchStep):raise ValueError('typed caller step')
            stack.remove(id(run))
        visit(node)
class RunDesk:
    def audit(self,node,catalog,batch_runner=None):
        from .runs import audit_run
        from .batch import run_batch
        catalog.validate_run(node)
        return audit_run(node,catalog,run_batch if batch_runner is None else batch_runner)
