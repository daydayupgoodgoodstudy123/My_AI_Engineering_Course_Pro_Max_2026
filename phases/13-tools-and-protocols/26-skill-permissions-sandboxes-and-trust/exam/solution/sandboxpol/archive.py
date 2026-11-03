"""Check an archive's member list before anything is extracted.

An archive is a flat list of members. Before the installer copies anything, the members must
form one clean package tree: <name>/SKILL.md as the entry point, everything else under <name>/.
"""
from __future__ import annotations

import posixpath
from dataclasses import dataclass

KINDS = ("file", "dir", "symlink", "hardlink", "fifo", "chardev", "blockdev", "socket")
LINKS = {"symlink", "hardlink"}
SPECIAL = {"fifo", "chardev", "blockdev", "socket"}


@dataclass(frozen=True)
class Member:
    path: str  # the member name as stored in the archive
    kind: str  # one of KINDS
    size: int = 0
    mode: int = 0o644  # the installer's business (see store.py); not checked here
    link: str = ""  # target of a symlink or hard link


@dataclass(frozen=True)
class Limits:
    max_files: int
    max_file_bytes: int
    max_total_bytes: int


@dataclass(frozen=True)
class Problem:
    code: str
    path: str


def check_archive(name: str, members: list[Member], limits: Limits) -> list[Problem]:
    """Return every problem with the archive, or [] when it is safe to extract.

    Paths are normalized first: a leading ./, repeated slashes and . segments go, and ..
    removes the segment before it. A directory member for the archive root itself (. or ./)
    is fine and ignored.

    Each member gets at most one path problem, and a member with a path problem gets no other:
      absolute-path      the path starts with /
      path-escape        the normalized path leaves the archive (a/../../x)
      outside-package    the normalized path is not <name> or under <name>/
    Any other member gets, in this order, each of these that applies:
      link               a symlink or hard link: packages may not contain links
      special-file       a fifo, a character or block device, or a socket
      file-too-large     a file bigger than max_file_bytes
      duplicate          a non-directory member at a path an earlier member already took
      not-a-directory    a member below an earlier non-directory member, a directory member
                         at an earlier non-directory member's path, or a non-directory
                         member at a path that earlier members already use as a directory
      extra-entry-point  a file named SKILL.md anywhere but <name>/SKILL.md

    After every member's problems, in archive order, come the problems of the archive as a
    whole, in this order, with an empty path except for the last:
      too-many-files       more than max_files members that are not directories
      too-large            files whose sizes add up to more than max_total_bytes
      missing-entry-point  no file member at <name>/SKILL.md (path: <name>/SKILL.md)
    Every member counts toward the two limits, whatever its other problems.
    """
    problems: list[Problem] = []
    seen: dict[str, str] = {}  # normalized path -> "dir" or "other"
    entry_point = f"{name}/SKILL.md"
    found_entry = False
    count = 0
    total = 0
    for member in members:
        is_dir = member.kind == "dir"
        if not is_dir:
            count += 1
        if member.kind == "file":
            total += member.size
        raw = member.path
        path = posixpath.normpath(raw) if raw else "."
        if raw.startswith("/"):
            problems.append(Problem("absolute-path", raw))
            continue
        if path == ".." or path.startswith("../"):
            problems.append(Problem("path-escape", raw))
            continue
        if path == "." and is_dir:
            continue
        if path != name and not path.startswith(name + "/"):
            problems.append(Problem("outside-package", raw))
            continue

        if member.kind in LINKS:
            problems.append(Problem("link", raw))
        elif member.kind in SPECIAL:
            problems.append(Problem("special-file", raw))
        elif member.kind == "file" and member.size > limits.max_file_bytes:
            problems.append(Problem("file-too-large", raw))

        ancestors = _ancestors(path)
        if not is_dir and path in seen and seen[path] != "dir":
            problems.append(Problem("duplicate", raw))
        if any(seen.get(parent) == "other" for parent in ancestors) or (
            seen.get(path) == ("other" if is_dir else "dir")
        ):
            problems.append(Problem("not-a-directory", raw))
        if member.kind == "file" and posixpath.basename(path) == "SKILL.md" and path != entry_point:
            problems.append(Problem("extra-entry-point", raw))
        if member.kind == "file" and path == entry_point:
            found_entry = True

        for parent in ancestors:
            seen.setdefault(parent, "dir")
        seen.setdefault(path, "dir" if is_dir else "other")

    if count > limits.max_files:
        problems.append(Problem("too-many-files", ""))
    if total > limits.max_total_bytes:
        problems.append(Problem("too-large", ""))
    if not found_entry:
        problems.append(Problem("missing-entry-point", entry_point))
    return problems


def _ancestors(path: str) -> list[str]:
    parts = path.split("/")
    return ["/".join(parts[:i]) for i in range(1, len(parts))]
