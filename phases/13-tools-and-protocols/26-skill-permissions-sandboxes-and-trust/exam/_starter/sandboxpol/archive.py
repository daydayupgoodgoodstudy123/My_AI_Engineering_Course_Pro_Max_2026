"""Check an archive's member list before anything is extracted.

An archive is a flat list of members. Before the installer copies anything, the members must
form one clean package tree: <name>/SKILL.md as the entry point, everything else under <name>/.
"""
from __future__ import annotations

from dataclasses import dataclass

KINDS = ("file", "dir", "symlink", "hardlink", "fifo", "chardev", "blockdev", "socket")


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
    raise NotImplementedError
