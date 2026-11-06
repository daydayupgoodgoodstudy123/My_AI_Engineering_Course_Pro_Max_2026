"""Checkpoints in a SQLite file: one row per step, one row per channel the step wrote."""
from __future__ import annotations

import base64
import json
import sqlite3
from typing import Any

from .checkpoint import Record

SCHEMA = """
CREATE TABLE IF NOT EXISTS steps (
    session TEXT NOT NULL,
    step INTEGER NOT NULL,
    node TEXT NOT NULL,
    calls TEXT NOT NULL,
    PRIMARY KEY (session, step)
);
CREATE TABLE IF NOT EXISTS writes (
    session TEXT NOT NULL,
    step INTEGER NOT NULL,
    channel TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (session, step, channel)
);
"""


def dumps(value: Any) -> str:
    """Encode a channel value as JSON text that loads() turns back into an equal value of the same types.

    Values are built from None, bool, int, float, str, bytes, list, tuple, set, frozenset and
    dict, with dict keys of any of these hashable types. Anything else raises TypeError.
    """
    return json.dumps(_tag(value))


def loads(text: str) -> Any:
    """The value dumps() encoded."""
    return _untag(json.loads(text))


def _tag(value: Any) -> Any:
    # Every container becomes a one-key object naming its type, a dict included, so a dict
    # that happens to look like a tag still reads back as a dict.
    kind = type(value)
    if value is None or kind in (bool, int, float, str):
        return value
    if kind is list:
        return [_tag(item) for item in value]
    if kind in (tuple, set, frozenset):
        return {kind.__name__: [_tag(item) for item in value]}
    if kind is bytes:
        return {"bytes": base64.b64encode(value).decode("ascii")}
    if kind is dict:
        return {"dict": [[_tag(key), _tag(item)] for key, item in value.items()]}
    raise TypeError(f"cannot checkpoint a value of type {kind.__name__}")


def _untag(data: Any) -> Any:
    if isinstance(data, list):
        return [_untag(item) for item in data]
    if not isinstance(data, dict):
        return data
    ((kind, body),) = data.items()
    if kind == "dict":
        return {_untag(key): _untag(item) for key, item in body}
    if kind == "bytes":
        return base64.b64decode(body)
    items = [_untag(item) for item in body]
    return {"tuple": tuple, "set": set, "frozenset": frozenset}[kind](items)


class SQLiteCheckpointer:
    """The checkpointer interface (put, records) on a SQLite file.

    A store opened on the same file later sees every record put before. A put is all or
    nothing: a value dumps() cannot encode raises TypeError and leaves no trace of the step.
    A session's steps are written once each, in order; anything else raises ValueError.
    """

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        self._db.executescript(SCHEMA)

    def put(self, session: str, record: Record) -> None:
        calls = dumps(tuple(record.calls))
        rows = [(session, record.step, channel, dumps(value)) for channel, value in record.writes.items()]
        with self._db:
            (latest,) = self._db.execute("SELECT MAX(step) FROM steps WHERE session = ?", (session,)).fetchone()
            if latest is not None and record.step <= latest:
                raise ValueError(f"{session}: step {record.step} is already written")
            self._db.execute("INSERT INTO steps VALUES (?, ?, ?, ?)", (session, record.step, record.node, calls))
            self._db.executemany("INSERT INTO writes VALUES (?, ?, ?, ?)", rows)

    def records(self, session: str) -> list[Record]:
        """The session's records in step order; empty for a session with none."""
        writes: dict[int, dict[str, Any]] = {}
        for step, channel, value in self._db.execute(
            "SELECT step, channel, value FROM writes WHERE session = ? ORDER BY step, rowid", (session,)
        ):
            writes.setdefault(step, {})[channel] = loads(value)
        return [
            Record(step, node, writes.get(step, {}), loads(calls))
            for step, node, calls in self._db.execute(
                "SELECT step, node, calls FROM steps WHERE session = ? ORDER BY step", (session,)
            )
        ]

    def close(self) -> None:
        self._db.close()
