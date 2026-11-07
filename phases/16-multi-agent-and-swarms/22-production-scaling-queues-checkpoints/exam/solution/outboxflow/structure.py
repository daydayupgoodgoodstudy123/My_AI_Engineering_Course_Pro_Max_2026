from .models import RouteAudit, GroupAudit

def expected_route(catalog,bound):
    """Cross-group paths rise to the common admin and descend; same-group traffic is direct."""
    m=bound.message
    a,b=bound.source_path,bound.destination_path
    if a==b:return (m.source,) if m.source==m.destination else (m.source,m.destination)
    common=0
    while common<min(len(a),len(b)) and a[common]==b[common]:common+=1
    admins=[catalog.admin(a[:k]) for k in range(len(a),common-1,-1)]
    admins += [catalog.admin(b[:k]) for k in range(common+1,len(b)+1)]
    route=[m.source]
    for uid in admins+[m.destination]:
        if route[-1]!=uid:route.append(uid)
    return tuple(route)

def audit_deployment(catalog,run):
    """Audit nested own routes and declared run outputs; address and origin binding are complete Given."""
    audits={}
    for uid in catalog.messages:
        bound=catalog.bind(uid);m=bound.message;reasons=[]
        route=expected_route(catalog,bound)
        if not bound.origin_valid:reasons.append('origin')
        if m.hops!=route:reasons.append('admin-route')
        a,b=bound.source_path,bound.destination_path
        for k in range(1,len(a)+1):
            path=a[:k]
            if b[:k]!=path and uid not in catalog.group(path).exports:
                reasons.append('undeclared-export:'+path[-1])
        audits[uid]=RouteAudit(uid,m.run,route,not reasons,tuple(reasons))
    def walk(group,path):
        path=path+(group.uid,)
        own=tuple(audits[uid] for uid in group.messages)
        children=tuple(walk(child,path) for child in group.children)
        outputs=[]
        for uid in group.exports:
            bound=catalog.bind(uid);m=bound.message
            if m.run==run and audits[uid].accepted and bound.source_path[:len(path)]==path and bound.destination_path[:len(path)]!=path:
                outputs.append(m)
        return GroupAudit(group.uid,path,own,children,tuple(outputs))
    return walk(catalog.root,())
