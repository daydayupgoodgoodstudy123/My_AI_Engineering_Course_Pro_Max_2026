"""Skill versions on disk, content-addressed.

root/objects/<sha256 hex> holds the code of a version, byte for byte; the name is the
SHA-256 of the code's UTF-8 bytes, so versions with the same code share one object.
root/manifest.json maps each skill name to its versions, oldest first:

    {"mine_ore": [{"version": 1, "code": "<sha256 hex>", "description": "...",
                   "tags": ["gather"], "depends_on": ["place_table", "craft_pickaxe@1"]}]}
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Iterable
from pathlib import Path

from .skills import Skill, compile_skill

_HEX = re.compile(r"[0-9a-f]{64}")


class StoreError(Exception):
    """The files on disk do not match the manifest."""


def code_hash(code: str) -> str:
    """The object name for a piece of code."""
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def save(skills: Iterable[Skill], root: str | os.PathLike) -> None:
    """Write every given version under root.

    skills holds every version of every skill, each skill's versions oldest first. An
    object is written only if it is not there yet, and stays even when no version uses it
    any more; the manifest is replaced.
    """
    root = Path(root)
    objects = root / "objects"
    objects.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, list[dict]] = {}
    for skill in skills:
        digest = code_hash(skill.code)
        path = objects / digest
        if not path.exists():
            _write_atomic(path, skill.code.encode("utf-8"))
        manifest.setdefault(skill.name, []).append(
            {
                "version": skill.version,
                "code": digest,
                "description": skill.description,
                "tags": list(skill.tags),
                "depends_on": list(skill.depends_on),
            }
        )
    _write_atomic(root / "manifest.json", (json.dumps(manifest, indent=2) + "\n").encode("utf-8"))


def load(root: str | os.PathLike) -> dict[str, list[Skill]]:
    """Read back every version saved under root, executable, each skill's versions oldest first.

    An object that is missing, or whose bytes do not hash to its name, raises StoreError
    naming the skill version that needs it ("mine_ore@2").
    """
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    library: dict[str, list[Skill]] = {}
    for name, records in manifest.items():
        versions = library[name] = []
        for record in records:
            ref = f"{name}@{record['version']}"
            digest = record["code"]
            if not _HEX.fullmatch(digest):
                raise StoreError(f"{ref}: {digest!r} is not an object name")
            try:
                data = (root / "objects" / digest).read_bytes()
            except FileNotFoundError:
                raise StoreError(f"{ref}: object {digest} is missing") from None
            if hashlib.sha256(data).hexdigest() != digest:
                raise StoreError(f"{ref}: object {digest} does not match its hash")
            code = data.decode("utf-8")
            versions.append(
                Skill(
                    name,
                    record["version"],
                    record["description"],
                    code,
                    tuple(record["tags"]),
                    tuple(record["depends_on"]),
                    compile_skill(code, f"{name} v{record['version']}"),
                )
            )
    return library


def _write_atomic(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)
