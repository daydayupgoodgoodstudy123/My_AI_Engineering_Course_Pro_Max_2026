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

import time
from collections.abc import Callable

from .memory import Mem0, Mem0Config


def save(mem: Mem0, path: str) -> None:
    """Write the three stores to path, replacing whatever the file held before.

    Everything reads back exactly: floats bit for bit, tags as the same tuple, every edge
    with its interval, in the order the edges were asserted.
    """
    raise NotImplementedError


def load(path: str, *, config: Mem0Config | None = None, clock: Callable[[], float] = time.time) -> Mem0:
    """Rebuild the Mem0 that save() wrote to path. Adding to it carries on where it left off."""
    raise NotImplementedError
