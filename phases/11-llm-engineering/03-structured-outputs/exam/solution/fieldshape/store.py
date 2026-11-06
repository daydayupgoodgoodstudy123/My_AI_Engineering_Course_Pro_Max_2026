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
        text = snapshot_text(model)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent, delete=False) as file:
                temporary = Path(file.name)
                file.write(text)
            os.replace(temporary, self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def load(self):
        """Return the saved ModelSpec via the supplied codec; no schema compile."""
        return parse_snapshot(self.path.read_text(encoding="utf-8"))
