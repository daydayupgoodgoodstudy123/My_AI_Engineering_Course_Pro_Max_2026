"""Version obligations and conservative three-way file upgrades."""
from __future__ import annotations

from .manifest import Manifest


def required_bump(base: Manifest, incoming: Manifest, migration_paths: set[str]) -> str:
    """Classify all added, removed or changed entries: none, patch, minor or major.

    Schema changes or changed paths named in migration_paths require major.
    Other non-doc changes require minor; doc-only changes require patch.
    Compare complete FileEntry values, including mode and component ownership.
    """
    old = {row.path: row for row in base.files}
    new = {row.path: row for row in incoming.files}
    changed = [p for p in old.keys() | new.keys() if old.get(p) != new.get(p)]
    if not changed:
        return "none"
    rows = [new[p] if p in new else old[p] for p in changed]
    if any(row.component == "schemas" or row.path in migration_paths for row in rows):
        return "major"
    return "patch" if all(row.component == "docs" for row in rows) else "minor"


def release_allowed(installed: str, proposed: str, bump: str) -> bool:
    """Require the exact next numeric major.minor.patch for the classified bump.

    Major resets minor/patch, minor resets patch, patch increments only patch.
    none requires the same version. Inputs are three nonnegative integer fields.
    """
    old = tuple(map(int, installed.split(".")))
    new = tuple(map(int, proposed.split(".")))
    major, minor, patch = old
    expected = {"none": old, "patch": (major, minor, patch + 1),
                "minor": (major, minor + 1, 0), "major": (major + 1, 0, 0)}[bump]
    return new == expected


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
    result = []
    for path in sorted(base.keys() | incoming.keys()):
        old, current, new = base.get(path), local.get(path), incoming.get(path)
        if current == new:
            status = "unchanged"
        elif old is None:
            status = "added" if current is None else "conflict"
        elif new is None:
            status = "removed" if current == old else "locally-modified"
        elif current == old:
            status = "update"
        elif new == old:
            status = "locally-modified"
        else:
            status = "conflict"
        result.append((path, status))
    return result
