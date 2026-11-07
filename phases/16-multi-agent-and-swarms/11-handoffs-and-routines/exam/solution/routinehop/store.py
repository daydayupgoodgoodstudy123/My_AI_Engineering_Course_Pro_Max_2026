"""Caller-owned continuation snapshots, with runtime callables rebound through the catalog."""
from .models import Continuation
from .codec import encode_receipt,decode_receipt,write_snapshot,read_snapshot
class RoutineStore:
    def __init__(self,directory):self.directory=directory
    def save(self,continuation):
        """Persist complete caller state and routine identity without serializing runtime functions."""
        document={'session':continuation.session,'active':continuation.active.name,'history':[encode_receipt(r)for r in continuation.history],'request_ids':continuation.request_ids}
        write_snapshot(self.directory,continuation.session,document)
    def load(self,session,catalog):
        """Reopen exact caller observations and rebind the active routine from this runtime catalog."""
        document=read_snapshot(self.directory,session)
        return Continuation(document['session'],catalog.agent(document['active']),tuple(decode_receipt(r)for r in document['history']),tuple(document['request_ids']))
