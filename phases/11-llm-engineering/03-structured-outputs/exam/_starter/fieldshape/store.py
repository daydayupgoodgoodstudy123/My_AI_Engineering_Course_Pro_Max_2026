"""Persist complete model descriptors as replaceable local JSON snapshots."""
import os
from pathlib import Path
import tempfile
from .codec import snapshot_text, parse_snapshot

class DescriptorStore:
    def __init__(self, path):
        self.path = Path(path)

    def save(self, model):
        """Replace one snapshot atomically after fully encoding the descriptor.

        Parent directory exists. Encode/replace failures propagate and leave
        the old snapshot readable and unchanged; remove temporary files.
        Preserve model/field order and explicit has_default metadata through
        the supplied codec. No default injection or numeric coercion.
        """
        raise NotImplementedError

    def load(self):
        """Return the saved ModelSpec via the supplied codec; no schema compile."""
        raise NotImplementedError
