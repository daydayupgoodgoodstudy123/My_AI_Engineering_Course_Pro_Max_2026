"""Extraction results kept on disk as one JSON snapshot."""
from __future__ import annotations

import json
import os
import tempfile
from decimal import Decimal
from typing import Any

from .outcome import ParsedResult
from .schema import ValidationError

_DECIMAL = "$decimal"  # {"$decimal": "120.00"} stands for Decimal("120.00")
# A payload object that would read back as a tag, such as a model-written {"$decimal": "1"}, is saved
# as {"$object": [[key, value]]}: object_hook never sees pairs, so they come back as the object itself.
_OBJECT = "$object"


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
        results = self._load()
        results[doc_id] = result
        self._save(results)

    def get(self, doc_id: str) -> ParsedResult:
        """The saved result for doc_id. Unknown ids raise KeyError."""
        return self._load()[doc_id]

    def doc_ids(self) -> list[str]:
        """Saved document ids, in the order they were first saved."""
        return list(self._load())

    def _load(self) -> dict[str, ParsedResult]:
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f, object_hook=_decode)
        except FileNotFoundError:
            return {}
        return {
            row["doc_id"]: ParsedResult(
                row["kind"],
                row["payload"],
                [ValidationError(tuple(loc), message) for loc, message in row["errors"]],
                row["raw"],
            )
            for row in data["results"]
        }

    def _save(self, results: dict[str, ParsedResult]) -> None:
        rows = [
            {
                "doc_id": doc_id,
                "kind": r.kind,
                "payload": _encode(r.payload),
                "errors": [[list(e.loc), e.message] for e in r.errors],
                "raw": r.raw,
            }
            for doc_id, r in results.items()
        ]
        text = json.dumps({"results": rows}, indent=1)
        directory = os.path.dirname(os.path.abspath(self.path))
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".results-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
        except BaseException:
            os.unlink(tmp)
            raise


def _encode(value: Any) -> Any:
    if isinstance(value, Decimal):
        return {_DECIMAL: str(value)}
    if isinstance(value, dict):
        encoded = {key: _encode(v) for key, v in value.items()}
        if len(encoded) == 1 and next(iter(encoded)) in (_DECIMAL, _OBJECT):
            return {_OBJECT: [[key, v] for key, v in encoded.items()]}
        return encoded
    if isinstance(value, list):
        return [_encode(v) for v in value]
    return value


def _decode(obj: dict) -> Any:
    if obj.keys() == {_DECIMAL}:
        return Decimal(obj[_DECIMAL])
    if obj.keys() == {_OBJECT}:
        return dict(obj[_OBJECT])
    return obj
