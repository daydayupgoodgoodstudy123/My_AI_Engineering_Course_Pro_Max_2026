"""Complete typed event intake and CSV writer/publication driver. No rainbow solver. Given."""
import csv
import io

def bound_events(events):
    events=tuple(events)
    if any(e.kind not in ('deploy','start','resume','failed_resume','finish','retire') for e in events):
        raise ValueError('known deployment event required')
    return events

async def publish_events(events,project):
    out=io.StringIO(newline='')
    writer=csv.writer(out,lineterminator='\n')
    writer.writerow(('event','thread_id','runtime_version','active_count','retire_allowed'))
    for row in project(bound_events(events)):
        writer.writerow(row)
    return out.getvalue()
