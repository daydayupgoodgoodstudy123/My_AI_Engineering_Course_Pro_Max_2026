"""Complete event/observation intake, tri-state severity, restricted RFC5424-style encoding and async driver. Given."""
from datetime import datetime,timedelta,timezone
import json
PHASES=('detected','diagnosed','validated')
def intake(events):
    events=tuple(events)
    for e in events:
        if not e.uid or any(c.isspace()for c in e.uid):raise ValueError('event token required')
        if e.phase not in PHASES:raise ValueError('typed phase required')
        if any(not isinstance(v,str)or '\r'in v or '\n'in v for v in (e.incident.uid,e.incident.root,e.incident.category,e.incident.action)):raise ValueError('single-line structured incident identifiers required')
        if e.phase=='validated':
            o=e.observation
            if o is None or o.action_uid!=e.incident.action or type(o.at)is not int or o.at<0 or not(o.cleared is None or type(o.cleared)is bool):raise ValueError('own post-action observation required')
    return events
def severity(event):
    if event.phase=='detected':return 3
    if event.phase=='diagnosed':return 4
    return 5 if event.observation.cleared is True else (3 if event.observation.cleared is False else 4)
def quote(value):return str(value).replace('\\','\\\\').replace('"','\\"').replace(']','\\]')
def format_row(row,index):
    event_uid,uid,root,phase,category,action,level,closing,note=row
    stamp=(datetime(2000,1,1,tzinfo=timezone.utc)+timedelta(seconds=index)).isoformat().replace('+00:00','Z')
    attrs=' '.join(k+'="'+quote(v)+'"'for k,v in (('uid',uid),('root',root),('phase',phase),('category',category),('action',action),('closing',str(closing).lower())))
    return '<'+str(8+level)+'>1 '+stamp+' localhost maststorm - '+event_uid+' [incident '+attrs+'] '+json.dumps(note,ensure_ascii=False)+'\n'
async def publish_incidents(events,projector):
    return ''.join(format_row(row,i)for i,row in enumerate(projector(intake(events))))
