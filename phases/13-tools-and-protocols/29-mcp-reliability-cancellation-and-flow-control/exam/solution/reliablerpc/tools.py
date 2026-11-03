"""Tools with side effects. Each one writes its effect through the connection it is given."""
from __future__ import annotations

import sqlite3
from typing import Any

ENTRIES_TABLE = """
CREATE TABLE IF NOT EXISTS entries (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    tool TEXT NOT NULL,
    account TEXT NOT NULL,
    cents INTEGER NOT NULL
)
"""


def charge_account(db: sqlite3.Connection, arguments: dict[str, Any], *, rpc_id: int | str) -> dict[str, Any]:
    """Charge arguments["cents"] to arguments["account"]: one entry, plus the receipt."""
    account, cents = arguments["account"], arguments["cents"]
    if type(cents) is not int or cents <= 0:
        raise ValueError("cents must be a positive integer")
    seq = db.execute(
        "INSERT INTO entries (tool, account, cents) VALUES ('charge_account', ?, ?)", (account, cents)
    ).lastrowid
    return {
        "receipt": f"charge-{seq:03d}",
        "rpcId": rpc_id,
        "charged": {"account": account, "cents": cents},
        "memo": arguments.get("memo"),
    }


def refund_account(db: sqlite3.Connection, arguments: dict[str, Any], *, rpc_id: int | str) -> dict[str, Any]:
    """Refund arguments["cents"] to arguments["account"]: one negative entry, plus the receipt."""
    account, cents = arguments["account"], arguments["cents"]
    if type(cents) is not int or cents <= 0:
        raise ValueError("cents must be a positive integer")
    seq = db.execute(
        "INSERT INTO entries (tool, account, cents) VALUES ('refund_account', ?, ?)", (account, -cents)
    ).lastrowid
    return {"receipt": f"refund-{seq:03d}", "rpcId": rpc_id, "refunded": {"account": account, "cents": cents}}


TOOLS = {"charge_account": charge_account, "refund_account": refund_account}
