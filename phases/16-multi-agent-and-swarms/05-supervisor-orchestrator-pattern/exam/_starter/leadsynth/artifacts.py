"""Durable assignment manifests over content-addressed summaries."""
from .models import Artifact,Claim
from .storage_support import ContentFiles

class ArtifactStore:
    def __init__(self,root):self.files=ContentFiles(root)
    def save(self,query_id,artifacts):
        """Persist exact summary objects plus ordered, query-specific assignments."""
        raise NotImplementedError
    def load(self,query_id):
        """Restore assignments in their declared order without merging shared content."""
        raise NotImplementedError
