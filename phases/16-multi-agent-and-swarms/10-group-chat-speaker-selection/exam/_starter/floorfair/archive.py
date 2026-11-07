"""Complete selector input/choice and utterance association snapshots by conversation."""
from .models import Snapshot,Speaker,Utterance
from .support import event_tag
from .db_support import transaction,encode,decode,restore_event,ensure_schema
class ChatArchive:
    def __init__(self,path):
        self.path=path
        with transaction(self.path)as db:ensure_schema(db)
    def save(self,snapshot):
        """Replace only this thread's full audit snapshot, preserving actual declaration order."""
        raise NotImplementedError
    def load(self,thread):
        """Reopen exact messages and their decision associations, including each decision's own input."""
        raise NotImplementedError
