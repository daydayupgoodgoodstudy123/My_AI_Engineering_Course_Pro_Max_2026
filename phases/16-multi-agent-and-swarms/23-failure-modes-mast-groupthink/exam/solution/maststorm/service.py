from .models import Detection,ReplayReport
from .primitives import categorize_incident,detect_groupthink,CircuitBreaker
from .breaker_given import categorize_incident as category_given,detect_groupthink as tags_given

def render_incident(incident,category,tags):
    return Detection(incident.uid,incident.root,incident.symptoms[incident.primary],category,tags)

def detect_incident(incident):
    category=categorize_incident(incident.symptoms)
    return render_incident(incident,category,detect_groupthink(incident.symptoms))

def detect_incident_given(incident):
    return render_incident(incident,category_given(incident.symptoms),tags_given(incident.symptoms))

class BreakerDesk:
    def replay(self,outcomes,window_size,threshold=.5):
        breaker=CircuitBreaker(window_size,threshold,3);rows=[]
        for i,success in enumerate(outcomes):
            allowed=breaker.allow(i)
            if allowed:breaker.record(success,i)
            rows.append((i,allowed,breaker.state,len(breaker.outcomes),breaker.failures))
        return ReplayReport(tuple(rows),tuple(breaker.outcomes),breaker.state,breaker.failures)
