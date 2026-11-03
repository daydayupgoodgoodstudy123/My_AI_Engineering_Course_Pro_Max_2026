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

from collections.abc import Iterable
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
        raise NotImplementedError

    def manifest(self, name: str) -> Manifest:
        """The installed manifest of name. Unknown names raise KeyError."""
        raise NotImplementedError

    def restore(self, name: str, dest: Path) -> None:
        """Write the installed package's files under dest, which must not exist yet."""
        raise NotImplementedError

    def plan_upgrade(
        self, name: str, source: Path, revision: str, reviewed_scripts: Iterable[str] = ()
    ) -> UpgradePlan:
        """Store the new version's contents and say what installing it would change.

        Nothing installed changes: the plan is for a reviewer to read first.
        """
        raise NotImplementedError

    def upgrade(self, name: str, plan: UpgradePlan) -> Manifest:
        """Install plan.target, the version that was reviewed, and return it.

        The plan must have been made against the manifest installed now; a plan made against
        another version raises ValueError. The source directory is not read again.
        """
        raise NotImplementedError
