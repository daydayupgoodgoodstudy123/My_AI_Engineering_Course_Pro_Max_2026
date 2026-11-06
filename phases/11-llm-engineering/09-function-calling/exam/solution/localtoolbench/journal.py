"""Buffered append-only local tool invocation audit."""
from dataclasses import asdict
from copy import deepcopy
from .models import Invocation
from .journal_codec import record_bytes,read_records
class AuditJournal:
    def __init__(self,path):self.path=path;self.pending=[]
    def append(self,invocation):
        """Stage an owned snapshot of every invocation, including structured failures."""
        self.pending.append(deepcopy(asdict(invocation)))
    def flush(self):
        """Given append writer for pending snapshots, preserving integer microseconds."""
        with self.path.open("ab") as handle:
            for row in self.pending:handle.write(record_bytes(row))
        self.pending.clear()
    def replay(self):
        """Read every flushed invocation in append order without deduplicating arguments."""
        return [Invocation(**row) for row in read_records(self.path)]
