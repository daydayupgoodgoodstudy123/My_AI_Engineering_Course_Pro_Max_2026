"""Binary64 local adapter archive with explicit shape and module identity."""
import struct
from .envelope import wrap_archive,read_archive
from .models import Adapter,valid_adapter
def encode_adapter(adapter):
    """Return exact binary64 A/B/alpha and UTF8 module metadata in a complete local archive."""
    raise NotImplementedError
def decode_adapter(raw):
    """Read exactly one complete archive, rejecting inconsistent or trailing bytes."""
    raise NotImplementedError
class AdapterArchive:
    def __init__(self,path):self.path=path
    def save(self,adapter):
        """Persist one complete validated adapter artifact."""
        raise NotImplementedError
    def load(self):
        """Reopen the same named adapter without numeric narrowing."""
        raise NotImplementedError
