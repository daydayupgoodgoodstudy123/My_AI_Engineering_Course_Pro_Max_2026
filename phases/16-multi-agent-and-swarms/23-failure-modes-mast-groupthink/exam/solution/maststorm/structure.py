from fractions import Fraction
from .models import AmplificationAudit,EdgeAudit,CascadeAudit

def audit_amplification(catalog):
    shorts=[];blocks=[];services=[]
    def walk(trace,path):
        own=short=blocked=0;edges=[];attempts=[]
        for attempt in trace.tries:
            inv=attempt.invocation;attempt_path=path+((trace.uid,attempt.ordinal),)
            own+=int(inv.actual);short+=int(inv.status=='short-circuit');blocked+=int(inv.status=='budget-exhausted')
            attempts.append((attempt.ordinal,inv.status,inv.actual,inv.success,inv.remaining))
            for child in attempt.children:edges.append(EdgeAudit(attempt.ordinal,child.uid,walk(child,attempt_path)))
            if inv.actual and inv.service not in services:services.append(inv.service)
            if inv.status=='short-circuit':shorts.append(attempt_path)
            if inv.status=='budget-exhausted':blocks.append(attempt_path)
        return AmplificationAudit(trace.uid,trace.service,trace.status,own,own+sum(e.audit.total_calls for e in edges),short,short+sum(e.audit.total_shortcircuits for e in edges),blocked,blocked+sum(e.audit.total_budget_blocks for e in edges),tuple(attempts),tuple(edges))
    report=catalog.report;roots=tuple(walk(trace,())for trace in report.nodes);total=sum(x.total_calls for x in roots)
    return CascadeAudit(report.root,report.incident,roots,total,tuple(services),Fraction(total,len(roots))if roots else Fraction(0),tuple(shorts),tuple(blocks))
