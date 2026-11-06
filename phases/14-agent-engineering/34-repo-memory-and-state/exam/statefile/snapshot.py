"""Crash-safe JSON snapshots: one document per file, kept as the system of record."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

NEW_FILE_MODE = 0o644


class CorruptSnapshot(ValueError):
    """The file exists but does not hold a JSON document."""


class Snapshot:
    """One JSON document in one file.

    The file is UTF-8 JSON indented by 2 spaces, with keys in the order the document has them,
    non-ASCII characters written as themselves and one newline at the end, so a reviewer reads
    real diffs. Values JSON cannot hold (a set, NaN, Infinity) raise before anything is written.

    save() never leaves a half-written file. It writes a temporary file in the same directory,
    named <file name>.<random>.tmp, flushes and fsyncs it, gives it the permission bits of the
    file it replaces (NEW_FILE_MODE for a new file), renames it over the target with os.replace,
    then fsyncs the directory so the rename itself survives a power cut. A save that fails
    leaves the old file and no temporary file. save() returns False, and does not touch the
    file, when the file already holds exactly the text it would write.

    Opening a Snapshot removes the temporary files that crashed saves left for this file, and
    nothing else: other files in the directory may belong to someone else.

    load() raises FileNotFoundError when nothing was ever saved, and CorruptSnapshot when the
    file is not a JSON document. It never guesses, and leaves a corrupt file for a human.
    """

    def __init__(self, path: str | os.PathLike) -> None:
        self.path = Path(path)

    def save(self, doc: Any) -> bool:
        raise NotImplementedError

    def load(self) -> Any:
        raise NotImplementedError
