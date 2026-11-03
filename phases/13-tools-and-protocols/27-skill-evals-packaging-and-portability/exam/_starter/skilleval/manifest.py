"""Install-tree integrity: a SHA-256 manifest of a bundle, and a check of an installed tree against it."""
from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path, PurePosixPath

from .provenance import SHA256, bytes_digest

RESERVED_MANIFEST_PATH = "assets/manifest.json"


def build_manifest(root: Path) -> dict[str, str]:
    """Map every file under root to "sha256:<hex>" of its bytes.

    Keys are canonical relative POSIX paths, such as "SKILL.md" and "references/policy.md".
    The reserved assets/manifest.json is left out: a file cannot carry a stable hash of itself.
    A symlink or a special file anywhere in the tree raises ValueError, and so does an empty tree.
    """
    if not root.is_dir() or root.is_symlink():
        raise ValueError("manifest root must be a regular directory")
    manifest: dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        folder = os.path.relpath(dirpath, root)
        for name in dirnames:
            if os.path.islink(os.path.join(dirpath, name)):
                raise ValueError(f"manifest tree contains a symlink: {os.path.join(folder, name)}")
        for name in sorted(filenames):
            path = Path(dirpath, name)
            relative = os.path.join(folder, name)
            if path.is_symlink():
                raise ValueError(f"manifest tree contains a symlink: {relative}")
            if not path.is_file():
                raise ValueError(f"manifest tree contains a special file: {relative}")
            if relative == RESERVED_MANIFEST_PATH:
                continue
            manifest[relative] = bytes_digest(path.read_bytes())
    if not manifest:
        raise ValueError("a manifest cannot describe an empty tree")
    return manifest


def verify_manifest(root: Path, expected: Mapping[str, str]) -> dict[str, object]:
    """Check the tree under root against an expected manifest.

    Keys must already be canonical relative POSIX paths: "./SKILL.md", backslashes, absolute
    paths and empty, "." or ".." segments are rejected, not normalized. The reserved manifest
    path must not be listed, and every digest is "sha256:" and 64 lowercase hex digits. The tree
    must hold exactly the listed files, each with its listed digest.

    Returns passed, issues, and the sorted missing, unexpected and mismatched paths.
    """
    issues: list[str] = []
    listed: dict[str, str] = {}
    for key, digest in expected.items():
        problem = _entry_problem(key, digest)
        if problem:
            issues.append(problem)
        else:
            listed[key] = digest
    missing: list[str] = []
    mismatched: list[str] = []
    for key, digest in listed.items():
        current = _current_digest(root, key)
        if current is None:
            missing.append(key)
        elif current != digest:
            mismatched.append(key)
    try:
        present = set(build_manifest(root))
    except ValueError as error:
        issues.append(str(error))
        present = set()
    unexpected = sorted(present - set(listed))
    return {
        "passed": not (issues or missing or unexpected or mismatched),
        "issues": issues,
        "missing": sorted(missing),
        "unexpected": unexpected,
        "mismatched": sorted(mismatched),
    }


def _current_digest(root: Path, key: str) -> str | None:
    """The digest the file at key has now, or None when the tree has no such regular file."""
    try:
        return build_manifest(root).get(key)
    except ValueError:
        return None


def _entry_problem(key: object, digest: object) -> str | None:
    if not isinstance(key, str) or not isinstance(digest, str):
        return "manifest paths and digests must be strings"
    relative = PurePosixPath(key)
    if (
        "\\" in key
        or relative.is_absolute()
        or any(part in {"", ".", ".."} for part in key.split("/"))
        or key != relative.as_posix()
    ):
        return f"invalid manifest path: {key!r}"
    if key == RESERVED_MANIFEST_PATH:
        return f"reserved manifest path must not be listed: {key!r}"
    if not SHA256.fullmatch(digest):
        return f"invalid manifest digest: {key!r}"
    return None
