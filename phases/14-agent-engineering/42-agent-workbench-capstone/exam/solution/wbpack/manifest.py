"""A TSV package manifest and its pinned VERSION file."""
from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileEntry:
    path: str
    sha256: str
    mode: int
    component: str


@dataclass(frozen=True)
class Manifest:
    version: str
    files: tuple[FileEntry, ...]


def save_manifest(directory: Path, manifest: Manifest) -> None:
    """Write VERSION and MANIFEST.tsv, preserving row order and all field values.

    Columns are path, sha256, mode, component, without a header. Mode is an
    octal permission string, such as 0755. TSV quoting follows Python csv.
    """
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "VERSION").write_text(manifest.version + "\n", encoding="utf-8")
    with (directory / "MANIFEST.tsv").open("w", encoding="utf-8", newline="") as fh:
        rows = csv.writer(fh, delimiter="\t", lineterminator="\n")
        for row in manifest.files:
            rows.writerow([row.path, row.sha256, format(row.mode, "04o"), row.component])


def load_manifest(directory: Path) -> Manifest:
    """Read both files; paths, digests, integer modes and components round-trip exactly."""
    with (directory / "MANIFEST.tsv").open(encoding="utf-8", newline="") as fh:
        rows = tuple(FileEntry(path, digest, int(mode, 8), component)
                     for path, digest, mode, component in csv.reader(fh, delimiter="\t"))
    return Manifest((directory / "VERSION").read_text(encoding="utf-8").strip(), rows)


def verify_manifest(root: Path, manifest: Manifest) -> list[str]:
    """Return every missing or digest-mismatched file path, in manifest order."""
    mismatches = []
    for row in manifest.files:
        path = root / row.path
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row.sha256:
            mismatches.append(row.path)
    return mismatches
