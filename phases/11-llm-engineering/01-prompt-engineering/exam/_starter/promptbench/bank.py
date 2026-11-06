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
        raise NotImplementedError

    def add(self, pattern: Pattern, version: str, system_override: str | None = None) -> str:
        """Save an independent revision and return its template-content digest."""
        raise NotImplementedError

    def get(self, name: str, version: str) -> Revision:
        """Read exact text and metadata, verifying the content digest."""
        raise NotImplementedError

    def revisions(self) -> list[Revision]:
        """Return all named versions in their original insertion order."""
        raise NotImplementedError

    def close(self) -> None:
        """Release the bank; successful adds are already durable."""
