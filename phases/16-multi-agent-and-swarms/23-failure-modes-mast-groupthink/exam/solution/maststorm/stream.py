from .wire_support import severity

def project_incidents(events):
    out=[]
    for e in events:
        r=e.incident
        closing=e.phase=='validated' and e.observation.cleared is True
        note=e.observation.note if e.phase=='validated' else ''
        out.append((e.uid,r.uid,r.root,e.phase,r.category,r.action,severity(e),closing,note))
    return tuple(out)
