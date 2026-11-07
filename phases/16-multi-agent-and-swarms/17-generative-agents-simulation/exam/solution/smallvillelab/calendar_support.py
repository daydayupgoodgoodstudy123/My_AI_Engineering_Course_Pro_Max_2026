"""Complete observation classification, UID binding, UTC adapter, calendar writer/parser and lifecycle."""
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from .models import CalendarObservation
class CalendarCatalog:
    def __init__(self,agents,venues,wall_origin=Decimal('0')):
        self.agents={a.uid:a for a in agents};self.venues={v.uid:v for v in venues};self.wall_origin=wall_origin
    def event_uid(self,segment_uid):return 'simulated-'+segment_uid+'@smallville.local'
    def agent_name(self,uid):return self.agents[uid].name
    def venue_name(self,uid):return self.venues[uid].label
    def time(self,tick):return(datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(seconds=int(self.wall_origin)+tick*60)).strftime('%Y%m%dT%H%M%SZ')
def calendar_observations(revision):
    return tuple(CalendarObservation(revision.state.uid,s,'CANCELLED'if s.status=='cancelled'else'CONFIRMED')for s in revision.state.plans)
def escape(value):return str(value).replace('\\','\\\\').replace('\n','\\n').replace(';','\\;').replace(',','\\,')
def unescape(value):
    result=[];i=0
    while i<len(value):
        if value[i]=='\\'and i+1<len(value):i+=1;result.append('\n'if value[i]=='n'else value[i])
        else:result.append(value[i])
        i+=1
    return ''.join(result)
def publish_calendar(observations,project):
    lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//SmallvilleLab//SIMULATED//EN']
    try:
        for observation in observations:
            row=project(observation);lines.append('BEGIN:VEVENT')
            for key in('UID','SEQUENCE','DTSTART','DTEND','SUMMARY','LOCATION','DESCRIPTION','STATUS','X-AGENT','X-SIMULATED'):
                value=row[key];lines.append(key+':'+(str(value)if key in('SEQUENCE','DTSTART','DTEND','STATUS','X-SIMULATED')else escape(value)))
            lines.append('END:VEVENT')
    finally:
        close=getattr(observations,'close',None)
        if close is not None:close()
    lines.append('END:VCALENDAR');return '\r\n'.join(lines)+'\r\n'
def parse_calendar(text):
    lines=text.split('\r\n');rows=[];row=None
    if lines[:2]!=['BEGIN:VCALENDAR','VERSION:2.0']or lines[-2:]!=['END:VCALENDAR','']:raise ValueError('complete calendar required')
    for line in lines[3:-2]:
        if line=='BEGIN:VEVENT':row={}
        elif line=='END:VEVENT':
            if set(row)!={'UID','SEQUENCE','DTSTART','DTEND','SUMMARY','LOCATION','DESCRIPTION','STATUS','X-AGENT','X-SIMULATED'}:raise ValueError('complete event required')
            rows.append(row);row=None
        else:
            key,value=line.split(':',1);row[key]=int(value)if key=='SEQUENCE'else unescape(value)
    if row is not None:raise ValueError('unfinished event')
    return tuple(rows)
