"""Ordered task-attempt snapshots with independent artifact members."""
from .models import Attempt,TaskEnvelope
from .artifact_codec import DirectoryFiles,encode_artifact,decode_artifact,member_name
class AttemptArchive:
    def __init__(self,path):self.files=DirectoryFiles(path)
    def save(self,attempts):
        """Save every declared attempt in order, retaining its own metadata and artifact.

        Artifact data belongs to the source wire domain: text or a strict JSON
        value tree (finite scalar values, lists and string-keyed dictionaries)."""
        entries=[]
        for index,item in enumerate(attempts):
            envelope=item.envelope;member=None;tag=None
            if envelope.artifact is not None:
                member=member_name(index);tag,payload=encode_artifact(envelope.artifact);self.files.put(member,payload)
            entries.append({'task_id':item.task_id,'attempt':item.attempt,'peer':item.peer,'card_version':item.card_version,'state':envelope.state,'observed_at':envelope.observed_at,'envelope_id':envelope.task_id,'member':member,'tag':tag})
        self.files.write_manifest(entries)
    def load(self):
        """Reopen the complete ordered attempt snapshot and its associated artifact data."""
        attempts=[]
        for entry in self.files.read_manifest():
            artifact=None if entry['member']is None else decode_artifact(entry['tag'],self.files.get(entry['member']))
            envelope=TaskEnvelope(entry['envelope_id'],entry['state'],artifact,entry['observed_at'])
            attempts.append(Attempt(entry['task_id'],entry['attempt'],entry['peer'],entry['card_version'],envelope))
        return tuple(attempts)
