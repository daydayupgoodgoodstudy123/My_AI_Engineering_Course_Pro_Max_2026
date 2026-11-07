"""Completed-evidence domain rows; TSV and async lifecycle are supplied."""
from .wire_support import path_text
class ProvenanceRows:
    def leaf_row(self,event):
        """Encode this actual sealed leaf execution and original obligation attribution."""
        raise NotImplementedError
    def branch_row(self,event):
        """Encode a branch audit, not a fabricated leaf execution or local task claim."""
        raise NotImplementedError
