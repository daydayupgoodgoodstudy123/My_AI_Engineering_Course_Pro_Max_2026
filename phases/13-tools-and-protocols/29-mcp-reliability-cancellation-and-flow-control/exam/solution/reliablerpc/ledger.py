"""An idempotency ledger in SQLite: one business intent runs once, whatever its JSON-RPC ids."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable, Mapping
from typing import Any

from .tools import ENTRIES_TABLE, TOOLS
from .wire import ReliabilityError

Tool = Callable[..., dict[str, Any]]

RECORDS_TABLE = """
CREATE TABLE IF NOT EXISTS idempotency_records (
    idempotency_key TEXT PRIMARY KEY,
    fingerprint TEXT NOT NULL,
    result_json TEXT NOT NULL
)
"""


class IdempotencyConflict(ReliabilityError):
    """An idempotency key came back with another tool or other arguments."""


class IdempotencyLedger:
    """Runs side-effecting tools at most once per idempotency key, in one SQLite file.

    Every server replica opens the same file. The key travels in the tool arguments as
    arguments["idempotencyKey"]; a call without one runs its tool every time.
    """

    def __init__(self, path: str, tools: Mapping[str, Tool] = TOOLS, *, timeout_s: float = 5.0) -> None:
        self.tools = dict(tools)
        # isolation_level=None: no implicit transactions, every BEGIN and COMMIT is explicit
        self._db = sqlite3.connect(path, timeout=timeout_s, isolation_level=None)
        self._db.execute(ENTRIES_TABLE)
        self._db.execute(RECORDS_TABLE)

    def call(self, name: str, arguments: dict[str, Any], *, rpc_id: int | str) -> dict[str, Any]:
        """Run tools[name](db, arguments, rpc_id=rpc_id) unless its idempotency key already ran.

        - A key names one business intent: one tool with one set of arguments. The same key with
          the same tool and the same arguments returns the stored result of the first call,
          including that call's rpcId, and runs nothing. Anything else under a stored key raises
          IdempotencyConflict and runs nothing. Arguments are the same when their JSON is,
          whatever the order of keys at any depth.
        - The key check, the tool's effect and the stored result commit together, in one
          transaction started with BEGIN IMMEDIATE, so two replicas racing on one key run it once.
          If the tool raises, nothing it wrote is kept and nothing is stored.
        - Every result, the first one included, is rebuilt from the stored JSON, so changing a
          returned dict changes nothing that later calls return.
        """
        tool = self.tools.get(name)
        if tool is None:
            raise ValueError(f"unknown tool {name!r}")
        key = arguments.get("idempotencyKey")
        fingerprint = _fingerprint(name, arguments)
        self._db.execute("BEGIN IMMEDIATE")
        try:
            if key is not None:
                stored = self._db.execute(
                    "SELECT fingerprint, result_json FROM idempotency_records WHERE idempotency_key = ?",
                    (key,),
                ).fetchone()
                if stored is not None:
                    if stored[0] != fingerprint:
                        raise IdempotencyConflict(f"idempotency key {key!r} was used for another call")
                    self._db.execute("COMMIT")
                    return json.loads(stored[1])
            result_json = json.dumps(tool(self._db, arguments, rpc_id=rpc_id), sort_keys=True)
            if key is not None:
                self._db.execute(
                    "INSERT INTO idempotency_records (idempotency_key, fingerprint, result_json) VALUES (?, ?, ?)",
                    (key, fingerprint, result_json),
                )
            self._db.execute("COMMIT")
        except BaseException:
            if self._db.in_transaction:
                self._db.execute("ROLLBACK")
            raise
        return json.loads(result_json)

    def lookup(self, idempotency_key: str) -> dict[str, Any] | None:
        """Reconcile by key: the stored result for idempotency_key, or None if it never committed."""
        row = self._db.execute(
            "SELECT result_json FROM idempotency_records WHERE idempotency_key = ?", (idempotency_key,)
        ).fetchone()
        return None if row is None else json.loads(row[0])

    def executions(self) -> int:
        """How many tool effects have committed."""
        return self._db.execute("SELECT COUNT(*) FROM entries").fetchone()[0]

    def close(self) -> None:
        self._db.close()


def _fingerprint(name: str, arguments: dict[str, Any]) -> str:
    canonical = json.dumps({"tool": name, "arguments": arguments}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
