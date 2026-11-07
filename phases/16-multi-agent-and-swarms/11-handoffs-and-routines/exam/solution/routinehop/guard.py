"""Online last-three typed handoff edge guard; complete audit is retained by the caller."""
from collections import deque
from .models import Transfer
from .support import is_two_agent_ring
class LastKLoopGuard:
    def __init__(self):self._edges=deque(maxlen=3);self.stopped=False
    def observe(self,event,audit):
        """Return sticky exit after three consecutive handoffs alternate between two routines.

        Ordinary notes do not consume a handoff slot; each guard belongs to one run.
        The caller supplies its complete already-appended audit for diagnostics.
        """
        if self.stopped:return True
        if isinstance(event,Transfer):self._edges.append(event)
        self.stopped=is_two_agent_ring(self._edges)
        return self.stopped
