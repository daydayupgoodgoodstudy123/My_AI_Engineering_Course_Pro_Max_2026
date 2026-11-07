"""Ordered task-attempt snapshots with independent artifact members."""
from .models import Attempt,TaskEnvelope
from .artifact_codec import DirectoryFiles,encode_artifact,decode_artifact,member_name
class AttemptArchive:
    def __init__(self,path):self.files=DirectoryFiles(path)
    def save(self,attempts):
        """Save every declared attempt in order, retaining its own metadata and artifact.

        Artifact data belongs to the source wire domain: text or a strict JSON
        value tree (finite scalar values, lists and string-keyed dictionaries)."""
        raise NotImplementedError
    def load(self):
        """Reopen the complete ordered attempt snapshot and its associated artifact data."""
        raise NotImplementedError
