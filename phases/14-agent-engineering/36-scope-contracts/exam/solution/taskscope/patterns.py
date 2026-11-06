"""Contract glob lists, matched against many touched paths."""
from __future__ import annotations

from collections.abc import Iterable, Iterator

from .globs import compile_glob, index_key


class PatternSet:
    """One glob list from a contract (allowed_files, forbidden_files, ...).

    A path matches the set when it matches at least one pattern. Patterns are
    contract globs (see globs.translate), matched against the whole normalized path.
    A project contract can carry thousands of globs, and a diff can touch thousands
    of files.
    """

    def __init__(self, patterns: Iterable[str]) -> None:
        self.patterns = list(patterns)
        self._exact: set[str] = set()
        self._by_directory: dict[str, list[str]] = {}
        for pattern in self.patterns:
            literal, directory = index_key(pattern)
            if literal is not None:
                self._exact.add(literal)
            else:
                self._by_directory.setdefault(directory, []).append(pattern)

    def matches(self, path: str) -> bool:
        if path in self._exact:
            return True
        by_directory = self._by_directory
        for directory in _directories(path):
            for pattern in by_directory.get(directory, ()):
                if compile_glob(pattern).match(path):
                    return True
        return False


def matches_any(path: str, patterns: Iterable[str]) -> bool:
    return PatternSet(patterns).matches(path)


def _directories(path: str) -> Iterator[str]:
    """"" and every directory above path: "a/b/c.py" gives "", "a", "a/b"."""
    yield ""
    cut = path.find("/")
    while cut != -1:
        yield path[:cut]
        cut = path.find("/", cut + 1)
