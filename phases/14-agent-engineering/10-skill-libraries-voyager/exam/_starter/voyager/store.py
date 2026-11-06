"""Skill versions on disk, content-addressed.

root/objects/<sha256 hex> holds the code of a version, byte for byte; the name is the
SHA-256 of the code's UTF-8 bytes, so versions with the same code share one object.
root/manifest.json maps each skill name to its versions, oldest first:

    {"mine_ore": [{"version": 1, "code": "<sha256 hex>", "description": "...",
                   "tags": ["gather"], "depends_on": ["place_table", "craft_pickaxe@1"]}]}
"""
from __future__ import annotations

import os
from collections.abc import Iterable

from .skills import Skill


class StoreError(Exception):
    """The files on disk do not match the manifest."""


def save(skills: Iterable[Skill], root: str | os.PathLike) -> None:
    """Write every given version under root.

    skills holds every version of every skill, each skill's versions oldest first. An
    object is written only if it is not there yet, and stays even when no version uses it
    any more; the manifest is replaced.
    """
    raise NotImplementedError


def load(root: str | os.PathLike) -> dict[str, list[Skill]]:
    """Read back every version saved under root, executable, each skill's versions oldest first.

    An object that is missing, or whose bytes do not hash to its name, raises StoreError
    naming the skill version that needs it ("mine_ore@2").
    """
    raise NotImplementedError
