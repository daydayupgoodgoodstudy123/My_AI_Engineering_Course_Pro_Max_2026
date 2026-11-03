"""The static paper fixture behind arxiv_search, kept as a CSV file."""
from __future__ import annotations

from dataclasses import dataclass

COLUMNS = ("arxiv_id", "title", "authors", "year", "source")


@dataclass(frozen=True)
class Paper:
    arxiv_id: str  # "2401.01230", "0912.0410", "cs/0112017", "2310.06770v2": always text
    title: str
    authors: tuple[str, ...]
    year: int
    source: str  # where the record came from, such as "arxiv-api 2026-10-30"


class Catalog:
    """Papers in a CSV file: one header row (COLUMNS), then one row per paper, in the order added.

    Every field reads back exactly as it was added. arXiv ids stay text, titles keep their
    commas, quotes and line breaks, authors keep every name, and the year reads back as an int.
    """

    def __init__(self, path: str) -> None:
        self.path = path

    def add(self, paper: Paper) -> None:
        """Append one paper. An arXiv id the catalog already holds raises ValueError."""
        raise NotImplementedError

    def papers(self) -> list[Paper]:
        """Every paper in the file, in the order added. A file that does not exist yet is an empty catalog."""
        raise NotImplementedError
