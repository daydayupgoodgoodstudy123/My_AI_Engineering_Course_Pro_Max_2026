"""Extraction results kept on disk as one JSON snapshot."""
from __future__ import annotations

from .outcome import ParsedResult


class ResultStore:
    """Extraction results by document id, in one JSON file at path.

    Every put() rewrites the whole snapshot: the new JSON goes to a temporary file in the same
    directory, which then replaces the snapshot with os.replace, so a crash leaves the old
    snapshot or the new one and never part of a file. A put() that raises changes nothing.
    Decimal amounts are saved as strings with all their digits; get() returns exactly the
    result that was put, raw reply included.
    """

    def __init__(self, path: str) -> None:
        self.path = path

    def put(self, doc_id: str, result: ParsedResult) -> None:
        """Save result for doc_id. A newer result for a document replaces the old one in its place."""
        raise NotImplementedError

    def get(self, doc_id: str) -> ParsedResult:
        """The saved result for doc_id. Unknown ids raise KeyError."""
        raise NotImplementedError

    def doc_ids(self) -> list[str]:
        """Saved document ids, in the order they were first saved."""
        raise NotImplementedError
