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
    raise NotImplementedError


def load_manifest(directory: Path) -> Manifest:
    """Read both files; paths, digests, integer modes and components round-trip exactly."""
    raise NotImplementedError


def verify_manifest(root: Path, manifest: Manifest) -> list[str]:
    """Return every missing or digest-mismatched file path, in manifest order."""
    raise NotImplementedError
