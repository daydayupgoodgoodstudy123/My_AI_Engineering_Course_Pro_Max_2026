"""Local JSON snapshot of a fixed design, usage reports and independent metadata."""
from dataclasses import asdict
import json
from pathlib import Path
from .models import snapshot_value
from .snapshot_codec import restore_snapshot

class SnapshotStore:
    def __init__(self,path):self.path=Path(path)
    def save(self,snapshot):
        """Write the complete typed JSON values without narrowing numbers or text.

        Preserve role/message/usage order, private versus addressed payloads,
        exact integer ids/counts, missing versus zero reports and finite float
        metadata. No crash-atomicity or concurrent-writer guarantee is made.
        """
        snapshot_value(snapshot)
        payload=asdict(snapshot)
        self.path.write_bytes(json.dumps(payload,ensure_ascii=False,allow_nan=False).encode("utf-8"))
    def load(self):
        """Restore all saved fields through the supplied typed codec, without refitting."""
        return restore_snapshot(json.loads(self.path.read_bytes()))
