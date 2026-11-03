"""The static paper fixture behind arxiv_search, kept as a CSV file."""
from __future__ import annotations

import csv
import json
import os
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
        if any(known.arxiv_id == paper.arxiv_id for known in self.papers()):
            raise ValueError(f"{paper.arxiv_id} is already in the catalog")
        new_file = not os.path.exists(self.path) or os.path.getsize(self.path) == 0
        with open(self.path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if new_file:
                writer.writerow(COLUMNS)
            writer.writerow(
                [
                    paper.arxiv_id,
                    paper.title,
                    json.dumps(list(paper.authors), ensure_ascii=False),
                    str(paper.year),
                    paper.source,
                ]
            )

    def papers(self) -> list[Paper]:
        """Every paper in the file, in the order added. A file that does not exist yet is an empty catalog."""
        try:
            f = open(self.path, newline="", encoding="utf-8")
        except FileNotFoundError:
            return []
        with f:
            rows = list(csv.reader(f))
        if not rows:
            return []
        if tuple(rows[0]) != COLUMNS:
            raise ValueError(f"{self.path} does not start with the header {','.join(COLUMNS)}")
        return [
            Paper(arxiv_id, title, tuple(json.loads(authors)), int(year), source)
            for arxiv_id, title, authors, year, source in rows[1:]
        ]
