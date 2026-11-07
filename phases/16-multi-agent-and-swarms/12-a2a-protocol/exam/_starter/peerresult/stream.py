"""Change-only domain event projection over observed local task snapshots."""
from .wire_support import public_artifact,is_terminal,final_payload
class TaskProjection:
    def __init__(self):self._previous_state=None;self._previous_artifact=None;self._final=False
    def events(self,snapshot):
        """Emit changed state then changed artifact, followed by at most one final event.

        A projection observes one task. Snapshots and explicit artifact tags are
        already provided by the correct transport and public-view dependencies.
        """
        raise NotImplementedError
