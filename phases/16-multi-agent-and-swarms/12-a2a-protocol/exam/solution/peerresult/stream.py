"""Change-only domain event projection over observed local task snapshots."""
from .wire_support import public_artifact,is_terminal,final_payload
class TaskProjection:
    def __init__(self):self._previous_state=None;self._previous_artifact=None;self._final=False
    def events(self,snapshot):
        """Emit changed state then changed artifact, followed by at most one final event.

        A projection observes one task. Snapshots and explicit artifact tags are
        already provided by the correct transport and public-view dependencies.
        """
        if self._final:return ()
        output=[];state=snapshot['state'];artifact=public_artifact(snapshot['artifact'])
        if state!=self._previous_state:output.append(('local-state',{'task_id':snapshot['id'],'state':state}));self._previous_state=state
        if artifact!=self._previous_artifact:output.append(('local-artifact',{'task_id':snapshot['id'],'artifact':artifact}));self._previous_artifact=artifact
        if is_terminal(snapshot):output.append(('local-final',final_payload(snapshot)));self._final=True
        return tuple(output)
