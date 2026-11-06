"""Contract glob lists, matched against many touched paths."""
from __future__ import annotations

import fnmatch
from collections.abc import Iterable


class PatternSet:
    """One glob list from a contract (allowed_files, forbidden_files, ...).

    A path matches the set when it matches at least one pattern. Patterns are matched
    with fnmatch.fnmatch against the whole path. A project contract can carry thousands
    of globs, and a diff can touch thousands of files.
    """

    def __init__(self, patterns: Iterable[str]) -> None:
        self.patterns = list(patterns)

    def matches(self, path: str) -> bool:
        return any(fnmatch.fnmatch(path, pattern) for pattern in self.patterns)


def matches_any(path: str, patterns: Iterable[str]) -> bool:
    return PatternSet(patterns).matches(path)
