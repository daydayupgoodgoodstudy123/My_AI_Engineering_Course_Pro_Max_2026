"""Candidate nested ant-path continuity, exact visited-edge credit and shared once-per-epoch trail updates."""
from .models import Trail,TrailState,PathAudit,ExpeditionAudit,TrailReport
def audit_expeditions(roots,catalog,state,rho,floor=0.):
    """Build every layer's path audit; deposit actual sealed amounts on valid visited trails with per-traversal multiplicity and shared epoch state."""
    catalog.validate(roots,state,rho,floor)
    def walk(node,current):
        before=current;audits=[]
        for path in node.own_paths:
            if path.epoch not in current.applied_epochs:
                current=TrailState(tuple(Trail(t.task_type,t.destination,t.edge_uid,max(floor,t.weight*(1-rho)))for t in current.trails),current.applied_epochs+(path.epoch,))
            decision=catalog.decision(path.decision_uid);position=path.start;visited=[];status='deposited'
            for uid in path.edges:
                edge=catalog.edge(uid)
                if edge.source!=position:status='discontinuous';break
                visited.append(uid);position=edge.target
            if status=='deposited'and position!=path.destination:status='wrong-destination'
            if status=='deposited'and not decision.accepted:status='rejected-learning'
            amount=decision.amount if status=='deposited'else 0.
            if status=='deposited':
                current=TrailState(tuple(Trail(t.task_type,t.destination,t.edge_uid,t.weight+amount*visited.count(t.edge_uid)if t.task_type==decision.task_type and t.destination==path.destination else t.weight)for t in current.trails),current.applied_epochs)
            audits.append(PathAudit(path.uid,status,tuple(visited),amount))
        children=[]
        for child in node.children:
            report,current=walk(child,current);children.append(report)
        return ExpeditionAudit(node.uid,tuple(audits),tuple(children),before,current),current
    reports=[]
    for root in roots:
        report,state=walk(root,state);reports.append(report)
    return TrailReport(tuple(reports),state)
