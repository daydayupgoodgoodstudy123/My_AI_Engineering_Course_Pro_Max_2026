"""Completed-evidence domain rows; TSV and async lifecycle are supplied."""
from .wire_support import path_text
class ProvenanceRows:
    def leaf_row(self,event):
        """Encode this actual sealed leaf execution and original obligation attribution."""
        return (event['task'],path_text(event['path']),'leaf',event['original_obligation'],event['leaf'].status.value,event['leaf'].leaf_id)
    def branch_row(self,event):
        """Encode a branch audit, not a fabricated leaf execution or local task claim."""
        return (event['task'],path_text(event['path']),'branch',event['audit']['obligation'],event['audit']['result'],'')
