"""dbm source/parent/child catalog with exact original typed metadata."""
import dbm
from .models import Catalog,Source,Parent,Child
from .codec import dbkey,encode,decode,record

class CatalogStore:
    def __init__(self,path):self.path=str(path)
    def save(self,catalog):
        """Persist exact source/parent/child records and microsecond metadata."""
        raise NotImplementedError("Part 2")
    def load(self):
        """Restore source insertion order and numeric parent/child ordinals."""
        raise NotImplementedError("Part 2")
