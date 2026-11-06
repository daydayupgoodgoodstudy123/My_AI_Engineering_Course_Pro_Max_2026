"""Per-unit evidence directories with exclusive byte-file creation."""
import base64
import os
from pathlib import Path


def _encode(value: str) -> str:
    """Encode an opaque name as an uppercase, case-fold-safe path component."""
    return base64.b32encode(value.encode("utf-8")).decode("ascii").rstrip("=")


def _decode(value: str) -> str:
    """Invert the provided uppercase Base32 name encoding."""
    return base64.b32decode(value + "=" * (-len(value) % 8)).decode("utf-8")


class EvidenceStore:
    """Opaque nonempty unit ids and filenames; bytes are never decoded as text.

    Use the provided case-fold-safe reversible encoders. A file may be
    created once only, including
    when an earlier file is empty. Reopening never removes or replaces evidence.
    """
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    def write(self, unit: str, name: str, data: bytes) -> None:
        """Create one file using O_EXCL; existing files raise FileExistsError."""
        raise NotImplementedError

    def read(self, unit: str, name: str) -> bytes:
        """Return exact bytes; missing evidence raises FileNotFoundError."""
        raise NotImplementedError

    def units(self) -> list[str]:
        """List exact unit ids in lexical order, independent of encoded name order."""
        raise NotImplementedError

    def files(self, unit: str) -> list[str]:
        """List exact evidence names for this unit in lexical order."""
        raise NotImplementedError
