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
    if path.startswith("/"):
        raise ValueError(f"absolute path: {path!r}")
    names: list[str] = []
    for segment in path.split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            if not names:
                raise ValueError(f"path leaves the repository: {path!r}")
            names.pop()
        else:
            names.append(segment)
    if not names:
        raise ValueError(f"not a file path: {path!r}")
    return "/".join(names)


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
    if not pattern:
        raise ValueError("empty glob")
    if pattern.startswith("/"):
        raise ValueError(f"absolute glob: {pattern!r}")
    if pattern.endswith("/"):
        pattern += "**"
    segments = pattern.split("/")
    last = len(segments) - 1
    parts: list[str] = []
    for i, segment in enumerate(segments):
        if segment == "**":
            parts.append(".+" if i == last else "(?:[^/]+/)*")
            continue
        parts.append(_segment(segment))
        if i < last:
            parts.append("/")
    return "".join(parts)


@functools.lru_cache(maxsize=65536)
def compile_glob(pattern: str) -> Glob:
    """Compile one contract glob (the dialect is described in translate)."""
    try:
        return Glob(pattern, re.compile(translate(pattern)))
    except re.error as exc:
        raise ValueError(f"bad glob {pattern!r}: {exc}") from None


_SPECIAL = re.compile(r"[*?\[\\]")


def index_key(pattern: str) -> tuple[str | None, str]:
    """How PatternSet files a glob: (literal, directory).

    literal is the one path the glob matches when it has no wildcard, else None.
    directory is the literal directory every match lies under ("" when the first
    segment already has a wildcard). Only globs that contain a backslash are parsed
    in full, so filing thousands of globs stays cheap.
    """
    if not pattern:
        raise ValueError("empty glob")
    if pattern.startswith("/"):
        raise ValueError(f"absolute glob: {pattern!r}")
    if pattern.endswith("/"):
        pattern += "**"
    found = _SPECIAL.search(pattern)
    if found is None:
        return pattern, ""
    if pattern[found.start()] != "\\":
        cut = pattern.rfind("/", 0, found.start())
        return None, pattern[:cut] if cut > 0 else ""
    names: list[str] = []
    for segment in pattern.split("/"):
        name = None if segment == "**" else _literal(segment)
        if name is None:
            return None, "/".join(names)
        names.append(name)
    return "/".join(names), ""


def _segment(segment: str) -> str:
    out: list[str] = []
    i, n = 0, len(segment)
    while i < n:
        c = segment[i]
        if c == "*":
            while i < n and segment[i] == "*":
                i += 1
            out.append("[^/]*")
            continue
        if c == "?":
            out.append("[^/]")
        elif c == "[":
            cls, i = _char_class(segment, i)
            out.append(cls)
            continue
        elif c == "\\":
            i += 1
            if i == n:
                raise ValueError(f"lone backslash at the end of {segment!r}")
            out.append(re.escape(segment[i]))
        else:
            out.append(re.escape(c))
        i += 1
    return "".join(out)


def _char_class(segment: str, start: int) -> tuple[str, int]:
    i = start + 1
    negate = i < len(segment) and segment[i] == "!"
    if negate:
        i += 1
    items: list[str] = []
    while True:
        if i >= len(segment):
            raise ValueError(f"unclosed [ in {segment!r}")
        c = segment[i]
        if c == "]" and items:
            break
        if c == "\\":
            i += 1
            if i >= len(segment):
                raise ValueError(f"unclosed [ in {segment!r}")
            c = segment[i]
        if i + 2 < len(segment) and segment[i + 1] == "-" and segment[i + 2] != "]":
            items.append(re.escape(c) + "-" + re.escape(segment[i + 2]))
            i += 3
        else:
            items.append(re.escape(c))
            i += 1
    body = "".join(items)
    return (f"[^{body}/]" if negate else f"(?!/)[{body}]"), i + 1


def _literal(segment: str) -> str | None:
    """The segment's text with escapes resolved, or None when it has a wildcard."""
    out: list[str] = []
    i, n = 0, len(segment)
    while i < n:
        c = segment[i]
        if c in "*?[":
            return None
        if c == "\\":
            i += 1
            if i == n:
                raise ValueError(f"lone backslash at the end of {segment!r}")
            c = segment[i]
        out.append(c)
        i += 1
    return "".join(out)
