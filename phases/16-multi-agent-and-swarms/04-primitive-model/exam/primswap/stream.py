"""Candidate domain projections of selected control and explicit terminal records."""
from copy import deepcopy
from .control import resolve_target

class DecisionProjection:
    def decision(self,event):
        """Describe the controlling source, its requested target and the actual message snapshot."""
        raise NotImplementedError

    def stop(self,event):
        """Encode the run's typed stop separately from an agent message or decision."""
        raise NotImplementedError
