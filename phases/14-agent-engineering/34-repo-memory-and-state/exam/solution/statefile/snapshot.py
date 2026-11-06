"""Crash-safe JSON snapshots: one document per file, kept as the system of record."""
from __future__ import annotations

import json
import os
import stat
import tempfile
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
        prefix, suffix = self.path.name + ".", ".tmp"
        if self.path.parent.is_dir():
            for entry in self.path.parent.iterdir():
                name = entry.name
                if (
                    name.startswith(prefix)
                    and name.endswith(suffix)
                    and len(name) > len(prefix) + len(suffix)
                    and entry.is_file()
                ):
                    entry.unlink()

    def save(self, doc: Any) -> bool:
        data = (json.dumps(doc, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
        try:
            if self.path.read_bytes() == data:
                return False
            mode = stat.S_IMODE(os.stat(self.path).st_mode)
        except FileNotFoundError:
            mode = NEW_FILE_MODE
        fd, tmp_name = tempfile.mkstemp(prefix=self.path.name + ".", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
                fh.flush()
                os.chmod(tmp_name, mode)
                os.fsync(fh.fileno())
            os.replace(tmp_name, self.path)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise
        dir_fd = os.open(self.path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
        return True

    def load(self) -> Any:
        data = self.path.read_bytes()
        try:
            return json.loads(data.decode("utf-8"), parse_constant=_not_json)
        except ValueError as exc:  # UnicodeDecodeError and JSONDecodeError are ValueErrors
            raise CorruptSnapshot(f"{self.path}: not a JSON document ({exc})") from exc


def _not_json(name: str) -> Any:
    raise ValueError(f"{name} is not JSON")
