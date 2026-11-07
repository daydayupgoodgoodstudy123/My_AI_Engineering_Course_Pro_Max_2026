from collections import deque
import math

def categorize_incident(symptoms):
    if symptoms.get('missing_role',False) or symptoms.get('ambiguous_goal',False):
        return 'spec'
    if symptoms.get('role_conflict',False) or symptoms.get('stale_context',False):
        return 'coord'
    if symptoms.get('bad_check',False):
        return 'verify'
    return 'unknown'

def detect_groupthink(symptoms):
    return tuple(tag for key,tag in (('style','style'),('lineup','lineup'),('consensus','consensus')) if symptoms.get(key,False))

class CircuitBreaker:
    """Logical-time CLOSED/OPEN/single-probe HALF_OPEN, strict rate threshold and bounded actual outcome window."""
    def __init__(self,window_size=100,threshold=.5,cooldown=3):
        if type(window_size) is not int or window_size<=0 or not math.isfinite(threshold) or not 0<=threshold<=1 or cooldown<0:
            raise ValueError('declared breaker configuration required')
        self.window_size=window_size;self.threshold=threshold;self.cooldown=cooldown
        self.outcomes=deque();self.failures=0;self.state='CLOSED';self.opened_at=0;self.probe_inflight=False
    def allow(self,now):
        if self.state=='OPEN':
            if now-self.opened_at<self.cooldown:return False
            self.state='HALF_OPEN'
        if self.state=='HALF_OPEN':
            if self.probe_inflight:return False
            self.probe_inflight=True
        return True
    def _observe(self,success):
        if len(self.outcomes)==self.window_size:
            expired=self.outcomes.popleft()
            self.failures-=not expired
        self.outcomes.append(success)
        self.failures+=not success
    def record(self,success,now):
        self._observe(success)
        if self.state=='HALF_OPEN':
            self.probe_inflight=False
            if success:
                self.state='CLOSED'
                self.outcomes.clear();self.failures=0
            else:
                self.state='OPEN';self.opened_at=now
        elif self.state=='CLOSED' and len(self.outcomes)==self.window_size and self.failures/len(self.outcomes)>self.threshold:
            self.state='OPEN';self.opened_at=now
