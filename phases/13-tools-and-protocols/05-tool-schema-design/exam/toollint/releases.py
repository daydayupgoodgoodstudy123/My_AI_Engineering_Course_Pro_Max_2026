"""Every published release of a tool registry, content-addressed on disk."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


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
    raise NotImplementedError


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
        raise NotImplementedError

    def load(self, version: str) -> list[dict]:
        """The tools of a release, in published order, value for value as they were published.

        An unknown version raises KeyError. A blob whose bytes do not match its digest raises
        ValueError.
        """
        raise NotImplementedError

    def versions(self) -> list[str]:
        """Every published version, lowest first, in semantic-version order."""
        raise NotImplementedError

    def history(self, name: str) -> list[tuple[str, str]]:
        """(version, digest) for every release that has the tool, lowest version first."""
        raise NotImplementedError
