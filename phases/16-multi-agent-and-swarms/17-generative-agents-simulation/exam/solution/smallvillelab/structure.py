"""Nested current-time execution with interval, open-hours and shared physical capacity admission."""
from .models import Movement,NodeAudit,ExecutionResult
def execute_nested_plan(roots,world,now):
    """Build every layer report while threading actual movements through one shared simulated world in declaration DFS order."""
    movements=[]
    def walk(o,current,parent=None,blocked=False):
        outside=parent is not None and not(parent[0]<=o.start and o.end<=parent[1])
        if o.segment is None:
            children=[]
            for child in o.children:
                report,current=walk(child,current,(o.start,o.end),blocked or outside);children.append(report)
            status='blocked'if blocked else'outside-parent'if outside else'complete'if all(c.status in('complete','moved','stayed','inactive')for c in children)else'partial'
            return NodeAudit(o.path,o.node.agent_uid,o.start,o.end,None,status,tuple(children)),current
        s=o.segment;agent=o.node.agent_uid
        if blocked:status='blocked'
        elif outside:status='outside-parent'
        elif s.status=='cancelled'or not(o.start<=now<o.end):status='inactive'
        else:
            venue=current.venue(s.venue_uid);origin=current.location(agent)
            if not any(a<=o.start and o.end<=b for a,b in venue.open_intervals):status='closed-venue'
            elif origin!=s.venue_uid and len(current.occupants(s.venue_uid))>=venue.capacity:status='full'
            elif origin==s.venue_uid:status='stayed'
            else:
                current=current.move(agent,s.venue_uid);movements.append(Movement(agent,s.uid,origin,s.venue_uid));status='moved'
        return NodeAudit(o.path,agent,o.start,o.end,s.uid,status),current
    reports=[]
    for root in roots:
        report,world=walk(root,world);reports.append(report)
    return ExecutionResult(tuple(reports),world,tuple(movements))
