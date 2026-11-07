def project_deployment(events):
    """Keep original run binding across successful or failed resume; retire only when drained."""
    bindings={}
    active=set()
    versions=[]
    rows=[]
    for event in events:
        if event.kind=='deploy':
            versions.append(event.version)
            version=event.version
        elif event.kind=='start':
            version=event.version
            bindings[event.run]=version
            active.add(event.run)
        elif event.kind in ('resume','failed_resume'):
            version=bindings[event.run]
        elif event.kind=='finish':
            version=bindings[event.run]
            active.discard(event.run)
        else:
            version=event.version
        count=sum(bindings[run]==version for run in active)
        rows.append((event.kind,event.run,version,count,event.kind=='retire' and count==0))
    return tuple(rows)
