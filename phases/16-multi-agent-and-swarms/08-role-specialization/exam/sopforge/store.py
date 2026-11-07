"""Persist distinct revision-bound role records through supplied SQLite primitives."""
from .models import Snapshot,Bundle
from .db import database,clear,write_record,read_records
from .bindings import require_bundle_links
class SOPStore:
    def __init__(self,path):self.path=path
    def save(self,snapshot):
        """Replace one complete snapshot; retain all spec and artifact revisions and role slots."""
        raise NotImplementedError
    def load(self):
        """Reopen artifact/report composite revision links, preserving declared snapshot order."""
        raise NotImplementedError
