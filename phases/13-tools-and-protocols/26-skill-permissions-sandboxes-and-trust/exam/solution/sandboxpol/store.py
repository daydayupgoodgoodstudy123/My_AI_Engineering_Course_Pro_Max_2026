"""Installed skill packages, kept content-addressed under one root directory.

    <root>/blobs/<sha256 hex>      the bytes of one file content, stored once however many files share it
    <root>/packages/<name>.json    the installation manifest of one package

A manifest records the source revision the package came from and, for every file, its path
relative to the package directory (POSIX, forward slashes), the SHA-256 of its bytes and
whether it is installed executable. A file is executable only when it is one of the reviewed
scripts and the source file has an executable bit. Directories are not recorded; they come
back with the files in them.

Restored files get mode 0o755 when executable and 0o644 otherwise, whatever mode the source had.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileEntry:
    sha256: str
    executable: bool


@dataclass(frozen=True)
class Manifest:
    name: str
    revision: str
    files: dict[str, FileEntry]


@dataclass(frozen=True)
class UpgradePlan:
    """What an upgrade would do, for a reviewer to see before anything installed is touched.

    added, changed and removed are sorted lists of paths. changed holds every installed file
    whose bytes or executable bit the upgrade would change. base is the manifest the plan was
    made against; target is the manifest the upgrade installs.
    """

    name: str
    base: Manifest
    target: Manifest
    added: list[str]
    changed: list[str]
    removed: list[str]


class InstallStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self._blobs = self.root / "blobs"
        self._packages = self.root / "packages"
        self._blobs.mkdir(parents=True, exist_ok=True)
        self._packages.mkdir(parents=True, exist_ok=True)

    def install(
        self, name: str, source: Path, revision: str, reviewed_scripts: Iterable[str] = ()
    ) -> Manifest:
        """Install the package in the source directory under name and return its manifest.

        reviewed_scripts are package paths, like scripts/build.sh. A name that is already
        installed raises FileExistsError: upgrades go through plan_upgrade.
        """
        if self._manifest_path(name).exists():
            raise FileExistsError(f"{name} is already installed")
        manifest = self._capture(name, Path(source), revision, reviewed_scripts)
        self._save(manifest)
        return manifest

    def manifest(self, name: str) -> Manifest:
        """The installed manifest of name. Unknown names raise KeyError."""
        try:
            text = self._manifest_path(name).read_text(encoding="utf-8")
        except FileNotFoundError:
            raise KeyError(name) from None
        data = json.loads(text)
        files = {
            path: FileEntry(entry["sha256"], entry["executable"])
            for path, entry in data["files"].items()
        }
        return Manifest(data["name"], data["revision"], files)

    def restore(self, name: str, dest: Path) -> None:
        """Write the installed package's files under dest, which must not exist yet."""
        manifest = self.manifest(name)
        dest = Path(dest)
        dest.mkdir(parents=True)
        for rel, entry in sorted(manifest.files.items()):
            data = (self._blobs / entry.sha256).read_bytes()
            if hashlib.sha256(data).hexdigest() != entry.sha256:
                raise ValueError(f"the stored bytes of {rel} do not match the manifest")
            path = dest / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            path.chmod(0o755 if entry.executable else 0o644)

    def plan_upgrade(
        self, name: str, source: Path, revision: str, reviewed_scripts: Iterable[str] = ()
    ) -> UpgradePlan:
        """Store the new version's contents and say what installing it would change.

        Nothing installed changes: the plan is for a reviewer to read first.
        """
        base = self.manifest(name)
        target = self._capture(name, Path(source), revision, reviewed_scripts)
        old, new = base.files, target.files
        return UpgradePlan(
            name=name,
            base=base,
            target=target,
            added=sorted(set(new) - set(old)),
            changed=sorted(path for path in set(old) & set(new) if old[path] != new[path]),
            removed=sorted(set(old) - set(new)),
        )

    def upgrade(self, name: str, plan: UpgradePlan) -> Manifest:
        """Install plan.target, the version that was reviewed, and return it.

        The plan must have been made against the manifest installed now; a plan made against
        another version raises ValueError. The source directory is not read again.
        """
        if plan.name != name or plan.base != self.manifest(name):
            raise ValueError(f"the plan for {name} was made against another installed version")
        self._save(plan.target)
        return plan.target

    def _manifest_path(self, name: str) -> Path:
        if not name or name.startswith(".") or "/" in name or "\\" in name:
            raise ValueError(f"invalid package name {name!r}")
        return self._packages / f"{name}.json"

    def _capture(
        self, name: str, source: Path, revision: str, reviewed_scripts: Iterable[str]
    ) -> Manifest:
        reviewed = set(reviewed_scripts)
        files: dict[str, FileEntry] = {}
        for path in sorted(_regular_files(source)):
            rel = path.relative_to(source).as_posix()
            data = path.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            blob = self._blobs / digest
            if not blob.exists():
                _write_atomic(blob, data)
            executable = rel in reviewed and bool(path.stat().st_mode & 0o111)
            files[rel] = FileEntry(digest, executable)
        return Manifest(name, revision, files)

    def _save(self, manifest: Manifest) -> None:
        data = {
            "name": manifest.name,
            "revision": manifest.revision,
            "files": {
                path: {"sha256": entry.sha256, "executable": entry.executable}
                for path, entry in sorted(manifest.files.items())
            },
        }
        text = json.dumps(data, indent=2, sort_keys=True) + "\n"
        _write_atomic(self._manifest_path(manifest.name), text.encode("utf-8"))


def _regular_files(root: Path) -> Iterator[Path]:
    for child in root.iterdir():
        info = child.lstat()
        if stat.S_ISDIR(info.st_mode):
            yield from _regular_files(child)
        elif stat.S_ISREG(info.st_mode):
            yield child
        else:
            raise ValueError(f"{child} is not a regular file or directory")


def _write_atomic(path: Path, data: bytes) -> None:
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)
