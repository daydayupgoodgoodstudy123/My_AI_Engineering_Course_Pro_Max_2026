"""A JSON snapshot of discovery, so a new session inspects only the packages that changed.

Packages are listed with package_dirs and inspected with inspect_package, as discover_scope does.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Union

from .discovery import Discovery, Rejection, Scope, SkillCandidate, inspect_package, package_dirs

SNAPSHOT_VERSION = 1


class DiscoveryCache:
    """Discovery results kept in one JSON snapshot file between sessions.

    discover(scope) returns exactly what discover_scope(scope) returns. A package is inspected
    again only when the SHA-256 of its SKILL.md bytes differs from the snapshot, or when the
    snapshot has nothing for it; size and modification time prove nothing. The results always
    carry the scope that discover() was called with. parsed lists, by directory name, the
    packages that the last discover() call inspected.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.parsed: list[str] = []

    def discover(self, scope: Scope) -> Discovery:
        packages = self._load()
        self.parsed = []
        found: list[Union[SkillCandidate, Rejection]] = []
        present: set[str] = set()
        for directory in package_dirs(scope.root):
            key = str(directory)
            present.add(key)
            digest = _digest(directory / "SKILL.md")
            record = packages.get(key)
            if record is None or record.get("digest") != digest:
                inspected = inspect_package(scope, directory)
                packages[key] = {"digest": digest, **_to_record(inspected)}
                self.parsed.append(directory.name)
                found.append(inspected)
            else:
                found.append(_from_record(record, scope, directory))
        for key in [key for key in packages if Path(key).parent == scope.root and key not in present]:
            del packages[key]
        self._save(packages)
        return Discovery(
            tuple(item for item in found if isinstance(item, SkillCandidate)),
            tuple(item for item in found if isinstance(item, Rejection)),
        )

    def _load(self) -> dict:
        try:
            snapshot = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except ValueError:
            return {}  # a damaged snapshot only costs a full inspection; discovery can rebuild it
        if not isinstance(snapshot, dict) or snapshot.get("version") != SNAPSHOT_VERSION:
            return {}
        return dict(snapshot.get("packages", {}))

    def _save(self, packages: dict) -> None:
        text = json.dumps({"version": SNAPSHOT_VERSION, "packages": packages}, indent=2, sort_keys=True)
        temporary = self.path.with_name(f".{self.path.name}.{os.getpid()}.tmp")
        temporary.write_text(text + "\n", encoding="utf-8")
        os.replace(temporary, self.path)


def _digest(skill_md: Path) -> str:
    if skill_md.is_symlink():
        return "symlink:" + os.readlink(skill_md)
    return hashlib.sha256(skill_md.read_bytes()).hexdigest()


def _to_record(found: Union[SkillCandidate, Rejection]) -> dict:
    if isinstance(found, Rejection):
        return {"kind": "rejected", "reason": found.reason}
    return {
        "kind": "candidate",
        "name": found.name,
        "description": found.description,
        "metadata": [list(pair) for pair in found.metadata],
    }


def _from_record(record: dict, scope: Scope, directory: Path) -> Union[SkillCandidate, Rejection]:
    if record["kind"] == "rejected":
        return Rejection(scope.name, directory, record["reason"])
    metadata = tuple((key, value) for key, value in record["metadata"])
    return SkillCandidate(record["name"], record["description"], scope.name, scope.rank, directory, metadata)
