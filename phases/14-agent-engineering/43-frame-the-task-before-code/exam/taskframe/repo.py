"""A read-only snapshot of a repository checkout."""
from __future__ import annotations


class Repo:
    """The files of one checkout, keyed by POSIX path from the repository root.

    Lines are numbered from 1, the way grep -n and editors number them: a line ends at
    "\\n", and a last line without a newline is still a line. A snapshot never changes.
    """

    def __init__(self, files: dict[str, str]) -> None:
        self._files = dict(files)

    def __contains__(self, path: object) -> bool:
        return path in self._files

    def paths(self) -> list[str]:
        return sorted(self._files)

    def lines(self, path: str) -> tuple[str, ...]:
        """The file's lines, without their newlines. An unknown path raises KeyError."""
        parts = self._files[path].split("\n")
        if parts[-1] == "":
            parts.pop()
        return tuple(parts)

    def line_count(self, path: str) -> int:
        return len(self.lines(path))

    def line(self, path: str, number: int) -> str:
        """Line `number` of a file, counted from 1. Outside the file raises IndexError."""
        lines = self.lines(path)
        if not 1 <= number <= len(lines):
            raise IndexError(f"{path} has no line {number}")
        return lines[number - 1]
