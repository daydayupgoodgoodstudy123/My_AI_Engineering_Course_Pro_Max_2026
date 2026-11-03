"""Every published release of a tool registry, content-addressed on disk."""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

VERSION = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")


def encode_descriptor(tool: dict) -> bytes:
    """The bytes a descriptor is stored and addressed by: UTF-8 JSON, sorted keys, no spaces."""
    return json.dumps(tool, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def descriptor_digest(tool: dict) -> str:
    """Hex SHA-256 of encode_descriptor(tool)."""
    return hashlib.sha256(encode_descriptor(tool)).hexdigest()


def parse_version(version: str) -> tuple[int, int, int]:
    """MAJOR.MINOR.PATCH as three integers.

    Exactly three dot-separated numbers in ASCII digits, without leading zeros. Anything else
    (a "v" prefix, a pre-release tag, surrounding whitespace) raises ValueError.
    """
    match = VERSION.fullmatch(version) if isinstance(version, str) else None
    if match is None:
        raise ValueError(f"not a MAJOR.MINOR.PATCH version: {version!r}")
    major, minor, patch = (int(part) for part in match.groups())
    return major, minor, patch


class ReleaseStore:
    """Releases of one tool registry, under one directory:

        blobs/<digest>           one file per distinct descriptor: its encode_descriptor() bytes,
                                 named by their SHA-256
        releases/<version>.json  one manifest per release: tool names mapped to digests

    A descriptor that several releases share is stored once. Nothing is kept in memory between
    calls, so a second ReleaseStore on the same directory sees every release.
    """

    def __init__(self, root: str) -> None:
        self.root = Path(root)
        self.blobs = self.root / "blobs"
        self.releases = self.root / "releases"
        self.blobs.mkdir(parents=True, exist_ok=True)
        self.releases.mkdir(parents=True, exist_ok=True)

    def publish(self, version: str, tools: list[dict]) -> dict[str, str]:
        """Store a release and return its manifest {tool name: digest}, in published order.

        Releases are immutable: publishing a version that exists raises ValueError, and so does
        a release with two tools of the same name or a malformed version. A refused release
        leaves nothing behind.
        """
        path = self._manifest_path(version)
        if path.exists():
            raise ValueError(f"release {version} already exists")
        manifest: dict[str, str] = {}
        blobs: list[tuple[str, bytes]] = []
        for tool in tools:
            name = tool["name"]
            if name in manifest:
                raise ValueError(f"release {version} has two tools named {name!r}")
            data = encode_descriptor(tool)
            digest = hashlib.sha256(data).hexdigest()
            manifest[name] = digest
            blobs.append((digest, data))
        for digest, data in blobs:
            blob = self.blobs / digest
            if not blob.exists():
                _write_atomic(blob, data)
        _write_atomic(path, json.dumps(manifest).encode("utf-8"))
        return manifest

    def load(self, version: str) -> list[dict]:
        """The tools of a release, in published order, value for value as they were published.

        An unknown version raises KeyError. A blob whose bytes do not match its digest raises
        ValueError.
        """
        tools = []
        for name, digest in self._manifest(version).items():
            data = (self.blobs / digest).read_bytes()
            if hashlib.sha256(data).hexdigest() != digest:
                raise ValueError(f"blob {digest} of {name!r} in release {version} is corrupt")
            tools.append(json.loads(data))
        return tools

    def versions(self) -> list[str]:
        """Every published version, lowest first, in semantic-version order."""
        found = []
        for path in self.releases.glob("*.json"):
            version = path.name.removesuffix(".json")
            if VERSION.fullmatch(version):
                found.append(version)
        return sorted(found, key=parse_version)

    def history(self, name: str) -> list[tuple[str, str]]:
        """(version, digest) for every release that has the tool, lowest version first."""
        out = []
        for version in self.versions():
            digest = self._manifest(version).get(name)
            if digest is not None:
                out.append((version, digest))
        return out

    def _manifest_path(self, version: str) -> Path:
        parse_version(version)
        return self.releases / f"{version}.json"

    def _manifest(self, version: str) -> dict[str, str]:
        path = self._manifest_path(version)
        if not path.exists():
            raise KeyError(version)
        return json.loads(path.read_bytes())


def _write_atomic(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)
