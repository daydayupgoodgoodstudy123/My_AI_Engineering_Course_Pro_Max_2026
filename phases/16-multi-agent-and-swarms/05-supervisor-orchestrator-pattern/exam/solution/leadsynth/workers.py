"""Worker artifact production and completed-duration observations."""
from dataclasses import replace
import heapq
from .models import Artifact

def pack_worker_result(task,observation):
    """Return the worker's narrow summary artifact, never its working context."""
    return Artifact(task.question_id,task.question,task.scope,observation.summary,observation.tokens,observation.seconds,False,observation.claims)

def apply_worker_cap(artifact,own_cap,team_mean_cap):
    """Mark a completed observation cut only when its own declared cap is exceeded."""
    return replace(artifact,cut=artifact.tokens>own_cap)

class DurationMedian:
    """Observe finite nonnegative sealed runtimes and return the exact prefix median."""
    def __init__(self):
        self._seen=[];self._low=[];self._high=[]
    def observe_duration(self,seconds):
        """Every completed observation participates, including duplicates and zero."""
        if not self._low or seconds<=-self._low[0]:heapq.heappush(self._low,-seconds)
        else:heapq.heappush(self._high,seconds)
        if len(self._low)>len(self._high)+1:heapq.heappush(self._high,-heapq.heappop(self._low))
        elif len(self._high)>len(self._low):heapq.heappush(self._low,-heapq.heappop(self._high))
        if len(self._low)==len(self._high):return (-self._low[0]+self._high[0])/2
        return -self._low[0]
