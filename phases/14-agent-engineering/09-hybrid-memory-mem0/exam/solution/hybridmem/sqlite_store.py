"""Save a Mem0 to a SQLite file and load it back.

One table per store, and the data-export job reads them directly. The columns it reads,
with their types:
  records  one row per record: rid TEXT, text TEXT, scope TEXT, user_id TEXT,
           session_id TEXT, agent_id TEXT, importance REAL, ts REAL,
           tags TEXT, last_read REAL
  kv       one row per KV key: user_id TEXT, fact_type TEXT, entity TEXT, and the
           rid TEXT it maps to
  edges    one row per edge, closed ones included: subject TEXT, relation TEXT,
           obj TEXT, rid TEXT, weight REAL, valid_from REAL, valid_to REAL
"""
from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Callable

from .graph import Edge
from .memory import KVKey, Mem0, Mem0Config, Record

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    seq INTEGER PRIMARY KEY,
    rid TEXT NOT NULL UNIQUE,
    text TEXT NOT NULL,
    scope TEXT NOT NULL,
    user_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    importance REAL NOT NULL,
    ts REAL NOT NULL,
    tags TEXT NOT NULL,
    last_read REAL
);
CREATE TABLE IF NOT EXISTS kv (
    user_id TEXT NOT NULL,
    fact_type TEXT NOT NULL,
    entity TEXT NOT NULL,
    rid TEXT NOT NULL,
    PRIMARY KEY (user_id, fact_type, entity)
);
CREATE TABLE IF NOT EXISTS edges (
    seq INTEGER PRIMARY KEY,
    subject TEXT NOT NULL,
    relation TEXT NOT NULL,
    obj TEXT NOT NULL,
    rid TEXT NOT NULL,
    weight REAL NOT NULL,
    valid_from REAL NOT NULL,
    valid_to REAL
);
"""

RECORD_COLUMNS = "rid, text, scope, user_id, session_id, agent_id, importance, ts, tags, last_read"
EDGE_COLUMNS = "subject, relation, obj, rid, weight, valid_from, valid_to"


def save(mem: Mem0, path: str) -> None:
    """Write the three stores to path, replacing whatever the file held before.

    Everything reads back exactly: floats bit for bit, tags as the same tuple, every edge
    with its interval, in the order the edges were asserted.
    """
    db = sqlite3.connect(path)
    try:
        db.executescript(SCHEMA)
        with db:
            for table in ("records", "kv", "edges"):
                db.execute(f"DELETE FROM {table}")
            db.executemany(
                f"INSERT INTO records (seq, {RECORD_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (seq, r.rid, r.text, r.scope, r.user_id, r.session_id, r.agent_id,
                     r.importance, r.ts, json.dumps(list(r.tags)), r.last_read)
                    for seq, r in enumerate(mem.vector.records())
                ],
            )
            db.executemany(
                "INSERT INTO kv (user_id, fact_type, entity, rid) VALUES (?, ?, ?, ?)",
                [(k.user_id, k.fact_type, k.entity, r.rid) for k, r in mem.kv.items()],
            )
            db.executemany(
                f"INSERT INTO edges (seq, {EDGE_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (seq, e.subject, e.relation, e.obj, e.rid, e.weight, e.valid_from, e.valid_to)
                    for seq, e in enumerate(mem.graph.all_edges())
                ],
            )
    finally:
        db.close()


def load(path: str, *, config: Mem0Config | None = None, clock: Callable[[], float] = time.time) -> Mem0:
    """Rebuild the Mem0 that save() wrote to path. Adding to it carries on where it left off."""
    mem = Mem0(config, clock=clock)
    db = sqlite3.connect(path)
    try:
        for row in db.execute(f"SELECT {RECORD_COLUMNS} FROM records ORDER BY seq"):
            *head, tags, last_read = row
            mem.vector.add(Record(*head, tuple(json.loads(tags)), last_read))
        for user_id, fact_type, entity, rid in db.execute("SELECT user_id, fact_type, entity, rid FROM kv"):
            mem.kv.put(KVKey(user_id, fact_type, entity), mem.record(rid))
        for subject, relation, obj, rid, weight, valid_from, valid_to in db.execute(
            f"SELECT {EDGE_COLUMNS} FROM edges ORDER BY seq"
        ):
            mem.graph.restore(Edge(subject, relation, obj, rid, valid_from, weight, valid_to))
    finally:
        db.close()
    mem._counter = max((int(r.rid[1:]) for r in mem.vector.records()), default=0)
    return mem
