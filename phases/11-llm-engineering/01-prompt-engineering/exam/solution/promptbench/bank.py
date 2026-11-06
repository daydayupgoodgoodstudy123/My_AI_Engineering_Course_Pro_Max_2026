"""Content-addressed template text and a versioned metadata manifest."""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from .prompts import Pattern


@dataclass(frozen=True)
class Revision:
    pattern: Pattern
    version: str
    digest: str
    system_override: str | None


class TemplateBank:
    """Persist named pattern versions in insertion order.

    The object digest is SHA-256 of exact UTF-8 template bytes. Several named
    versions may share an object while keeping independent metadata. Reusing
    the same (name, version) raises ValueError; unknown versions raise KeyError.
    """

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        self.objects = self.directory / "objects"
        self.objects.mkdir(parents=True, exist_ok=True)
        self.manifest = self.directory / "manifest.json"
        self._records = json.loads(self.manifest.read_bytes()) if self.manifest.exists() else []

    def add(self, pattern: Pattern, version: str, system_override: str | None = None) -> str:
        """Save an independent revision and return its template-content digest."""
        if any(row["name"] == pattern.name and row["version"] == version for row in self._records):
            raise ValueError("pattern version already exists")
        payload = pattern.template.encode("utf-8")
        digest = hashlib.sha256(payload).hexdigest()
        (self.objects / digest).write_bytes(payload)
        record = {
            "name": pattern.name, "version": version, "digest": digest,
            "variables": list(pattern.variables), "temperature": pattern.temperature,
            "description": pattern.description, "system_override": system_override,
        }
        next_records = self._records + [record]
        temporary = self.directory / "manifest.tmp"
        temporary.write_bytes(json.dumps(next_records, ensure_ascii=False).encode("utf-8"))
        os.replace(temporary, self.manifest)
        self._records = next_records
        return digest

    def get(self, name: str, version: str) -> Revision:
        """Read exact text and metadata, verifying the content digest."""
        for row in self._records:
            if row["name"] == name and row["version"] == version:
                payload = (self.objects / row["digest"]).read_bytes()
                if hashlib.sha256(payload).hexdigest() != row["digest"]:
                    raise ValueError("template content digest mismatch")
                pattern = Pattern(row["name"], payload.decode("utf-8"), tuple(row["variables"]),
                                  row["temperature"], row["description"])
                return Revision(pattern, row["version"], row["digest"], row["system_override"])
        raise KeyError((name, version))

    def revisions(self) -> list[Revision]:
        """Return all named versions in their original insertion order."""
        return [self.get(row["name"], row["version"]) for row in self._records]

    def close(self) -> None:
        """Release the bank; successful adds are already durable."""
