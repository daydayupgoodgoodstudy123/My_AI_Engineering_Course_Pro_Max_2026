"""Worker artifact production and completed-duration observations."""
from dataclasses import replace
import heapq
from .models import Artifact

def pack_worker_result(task,observation):
    """Return the worker's narrow summary artifact, never its working context."""
    return Artifact(task.question_id,task.question,task.scope,observation.working_context,observation.tokens,observation.seconds,False,observation.claims)

def apply_worker_cap(artifact,own_cap,team_mean_cap):
    """Mark a completed observation cut only when its own declared cap is exceeded."""
    return replace(artifact,cut=artifact.tokens>team_mean_cap)

class DurationMedian:
    """Observe finite nonnegative sealed runtimes and return the exact prefix median."""
    def __init__(self):
        self._seen=[];self._low=[];self._high=[]
    def observe_duration(self,seconds):
        """Every completed observation participates, including duplicates and zero."""
        self._seen.append(seconds)
        ordered=sorted(self._seen);n=len(ordered)
        return ordered[n//2] if n%2 else (ordered[n//2-1]+ordered[n//2])/2
