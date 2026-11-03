"""An idempotency ledger in SQLite: one business intent runs once, whatever its JSON-RPC ids."""
from __future__ import annotations

import sqlite3
from collections.abc import Callable, Mapping
from typing import Any

from .tools import ENTRIES_TABLE, TOOLS
from .wire import ReliabilityError

Tool = Callable[..., dict[str, Any]]


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
        # TODO: the idempotency records

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
        raise NotImplementedError

    def lookup(self, idempotency_key: str) -> dict[str, Any] | None:
        """Reconcile by key: the stored result for idempotency_key, or None if it never committed."""
        raise NotImplementedError

    def executions(self) -> int:
        """How many tool effects have committed."""
        return self._db.execute("SELECT COUNT(*) FROM entries").fetchone()[0]

    def close(self) -> None:
        self._db.close()
