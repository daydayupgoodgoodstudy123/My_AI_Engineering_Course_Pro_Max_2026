"""Append-only component revisions with a compact current-state checkpoint."""
from pathlib import Path
import json
from .codec import encode_component, decode_component

class ComponentLog:
    def __init__(self, path):
        self.path = Path(path)
        self.checkpoint_path = self.path.with_suffix(self.path.suffix + ".checkpoint.json")

    def replay(self):
        """Return latest live components in first-seen slot order.

        Read checkpoint before log; covered older revisions are ignored.
        A record equal in revision to the current live value must have the
        same contents, otherwise ValueError. This is state replay, not a
        complete historical revision-integrity audit.
        Updates replace a slot without moving it or duplicating its tokens.
        Preserve supplied codec text, role, revision and provenance exactly.
        """
        raise NotImplementedError

    def append(self, component):
        """Validate then append one strictly newer revision; stale writes fail.

        One UTF-8 JSON line per component. A new process replays committed
        text; successful append closes its file before returning.
        """
        raise NotImplementedError

    def checkpoint(self):
        """Write ordered live state, then clear covered log entries.

        Replay tolerates old covered lines if a checkpoint/log-clear gap is
        observed. No transaction, fsync/crash durability or partial-line repair
        is promised by this local exercise format.
        """
        raise NotImplementedError
