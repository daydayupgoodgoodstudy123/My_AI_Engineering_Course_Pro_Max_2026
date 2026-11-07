"""Persist full ordered immutable entry history and its provenance fields."""
from .models import Entry
from .ledger_support import LedgerDriver,encode_metadata,decode_metadata
def encode_entries(entries):
    """Build every entry document in declaration order, including retired and repeated versions."""
    raise NotImplementedError
def decode_entries(documents):
    """Reconstruct original IDs, content and provenance without active filtering or reindexing."""
    raise NotImplementedError
class ProvenanceLog:
    def __init__(self,path):self._driver=LedgerDriver(path)
    def append(self,pool_view,finding_view):self._driver.append(pool_view,finding_view,encode_entries)
    def reopen(self):return self._driver.reopen(decode_entries)
