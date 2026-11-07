"""Caller-owned continuation snapshots, with runtime callables rebound through the catalog."""
from .models import Continuation
from .codec import encode_receipt,decode_receipt,write_snapshot,read_snapshot
class RoutineStore:
    def __init__(self,directory):self.directory=directory
    def save(self,continuation):
        """Persist complete caller state and routine identity without serializing runtime functions."""
        raise NotImplementedError
    def load(self,session,catalog):
        """Reopen exact caller observations and rebind the active routine from this runtime catalog."""
        raise NotImplementedError
