"""Version obligations and conservative three-way file upgrades."""
from __future__ import annotations

from .manifest import Manifest


def required_bump(base: Manifest, incoming: Manifest, migration_paths: set[str]) -> str:
    """Classify all added, removed or changed entries: none, patch, minor or major.

    Schema changes or changed paths named in migration_paths require major.
    Other non-doc changes require minor; doc-only changes require patch.
    Compare complete FileEntry values, including mode and component ownership.
    """
    raise NotImplementedError


def release_allowed(installed: str, proposed: str, bump: str) -> bool:
    """Require the exact next numeric major.minor.patch for the classified bump.

    Major resets minor/patch, minor resets patch, patch increments only patch.
    none requires the same version. Inputs are three nonnegative integer fields.
    """
    raise NotImplementedError


def upgrade_plan(base: dict[str, str], local: dict[str, str],
                 incoming: dict[str, str]) -> list[tuple[str, str]]:
    """Classify the sorted union of base/incoming paths; local-only paths are untouched.

    Hashes are opaque strings; absent keys mean absent files. A file already
    equal to incoming is unchanged. An incoming removal is safe only if local
    equals base; an already absent removed file is unchanged. A local-only
    edit/deletion is locally-modified; divergent local and upstream edits are
    conflict. New upstream paths are added unless colliding with different
    local contents. Other clean upstream edits are update.
    """
    raise NotImplementedError
