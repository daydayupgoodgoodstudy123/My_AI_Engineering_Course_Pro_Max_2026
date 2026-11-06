"""Content-addressed redacted payloads with independent safe audit manifests."""
import json
from .contracts import StoredTranscript,manifest_path,payload_bytes,content_key,atomic_bytes,json_bytes
from .audit_codec import audit_to_records,audit_from_records
class TranscriptStore:
    def __init__(self,root):self.root=root;self.root.mkdir(parents=True,exist_ok=True)
    def save(self,key,transcript):
        """Save redacted UTF-8 content and its original-offset safe audit only.

        Runtime Transcript.original is sensitive and must never be persisted.
        Equal redacted payloads share a content-addressed blob, while each key
        owns its independent safe audit manifest. Complete AuditSpan field encoding,
        exact confidence spelling, validation and restoration are GIVEN by
        audit_to_records/audit_from_records. Use that codec; candidate work is
        safe outer manifest composition, payload selection, per-key ownership
        and digest-checked restoration. No filesystem security guarantee.
        """
        path=manifest_path(self.root,key)
        data=payload_bytes(transcript.redacted);digest=content_key(data)
        spans=audit_to_records(transcript.spans)
        atomic_bytes(self.root/"blobs"/digest,data)
        atomic_bytes(path,json_bytes({"payload":digest,"spans":spans}))
    def load(self,key):
        """Load exact redacted text and its key's complete audit; raw PII is not stored."""
        manifest=json.loads(manifest_path(self.root,key).read_bytes())
        data=(self.root/"blobs"/manifest["payload"]).read_bytes()
        if content_key(data)!=manifest["payload"]:raise ValueError("payload digest")
        spans=audit_from_records(manifest["spans"])
        return StoredTranscript(data.decode("utf-8"),spans)
