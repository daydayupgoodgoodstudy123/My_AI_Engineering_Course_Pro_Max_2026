"""The contract glob dialect, and repository path normalization."""
from __future__ import annotations

import functools
import re


class Glob:
    """A compiled contract glob. Build one with compile_glob."""

    def __init__(self, pattern: str, regex: re.Pattern[str]) -> None:
        self.pattern = pattern
        self.regex = regex

    def match(self, path: str) -> bool:
        """True when the whole path matches. path is already normalized (normalize_path)."""
        return self.regex.fullmatch(path) is not None

    def __repr__(self) -> str:
        return f"Glob({self.pattern!r})"


def normalize_path(path: str) -> str:
    """Normalize a repository path the way git writes it.

    Paths are relative to the repository root and use "/". Empty and "." segments are
    dropped (so "./", repeated slashes and a trailing slash go away), and "a/../b"
    becomes "b". A path that is absolute, climbs out of the repository with "..", or
    is empty once normalized raises ValueError. Every other segment is a name and is
    kept exactly as written: "..notes" and "..." are ordinary names, and case matters.

    scope_check normalizes every touched path before matching it, and a touched path
    that this rejects is forbidden.
    """
    raise NotImplementedError


def translate(pattern: str) -> str:
    """Translate one contract glob into a regular expression for re.fullmatch.

    A glob is matched against the whole normalized repository path.

    - "*" matches any run of characters except "/"; "?" matches one character except "/".
    - "[abc]", "[a-z]" and "[!abc]" match one character in (or not in) the class.
      A class never matches "/".
    - A backslash makes the next character literal: "app/\\[slug\\]/page.tsx" is the
      file app/[slug]/page.tsx.
    - "**" as a whole segment matches zero or more directories: "**/notes.md" matches
      "notes.md" and "a/b/notes.md", and "a/**/b" matches "a/b" and "a/x/y/b".
      "dir/**" at the end matches every file below dir. Inside a segment ("a**b"),
      "**" is the same as "*".
    - A trailing "/" names a directory: "docs/" is "docs/**".
    - Matching is case-sensitive.

    An empty or absolute pattern, a lone backslash at the end of a segment, and a "["
    without its closing "]" raise ValueError.
    """
    raise NotImplementedError


@functools.lru_cache(maxsize=65536)
def compile_glob(pattern: str) -> Glob:
    """Compile one contract glob (the dialect is described in translate)."""
    try:
        return Glob(pattern, re.compile(translate(pattern)))
    except re.error as exc:
        raise ValueError(f"bad glob {pattern!r}: {exc}") from None
