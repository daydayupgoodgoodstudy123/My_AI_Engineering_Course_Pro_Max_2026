"""Drafts that any replica can load, kept in one SQLite file that every replica opens.

Request A may reach replica 1 and request B replica 2, so a draft never lives only in one
replica's memory. It is stored under a server-minted handle, which goes back to the client in an
ordinary tool result and comes in again as an ordinary tool argument.
"""
from __future__ import annotations

import secrets
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass

from .protocol import Principal

DEFAULT_TTL_MS = 15 * 60 * 1000

SCHEMA = """
CREATE TABLE IF NOT EXISTS drafts (
    handle TEXT PRIMARY KEY,
    subject TEXT NOT NULL,
    tenant TEXT NOT NULL,
    version INTEGER NOT NULL,
    text TEXT NOT NULL,
    expires_at_ms INTEGER NOT NULL
)
"""


@dataclass(frozen=True)
class Draft:
    handle: str
    owner: Principal
    version: int
    text: str
    expires_at_ms: int


class UnknownHandle(LookupError):
    """There is no live draft under this handle that this caller may use."""


class VersionConflict(Exception):
    """Someone saved the draft after the caller read it."""

    def __init__(self, current: int) -> None:
        super().__init__(f"the draft is at version {current}")
        self.current = current


class DraftStore:
    """The shared draft table, through this replica's own connection.

    clock() returns the current time in integer milliseconds. A draft expires ttl_ms after it is
    created; saving does not extend it.
    """

    def __init__(self, path: str, *, clock: Callable[[], int], ttl_ms: int = DEFAULT_TTL_MS) -> None:
        self._db = sqlite3.connect(path)
        self._clock = clock
        self._ttl_ms = ttl_ms
        with self._db:
            self._db.execute(SCHEMA)

    def create(self, owner: Principal, text: str) -> Draft:
        """Store a new draft, version 1, under a fresh handle, and return it.

        Handles are opaque and unguessable: at least 128 random bits from the secrets module, so
        no two replicas ever mint the same one.
        """
        draft = Draft(secrets.token_urlsafe(32), owner, 1, text, self._clock() + self._ttl_ms)
        with self._db:
            self._db.execute(
                "INSERT INTO drafts (handle, subject, tenant, version, text, expires_at_ms)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (draft.handle, owner.subject, owner.tenant, draft.version, text, draft.expires_at_ms),
            )
        return draft

    def get(self, owner: Principal, handle: str) -> Draft:
        """The draft as last saved through any replica.

        A handle that was never issued, has expired, or belongs to another subject or tenant
        raises the same UnknownHandle, so the caller cannot tell these apart. A draft is live
        while clock() is before its expires_at_ms.
        """
        row = self._db.execute(
            "SELECT version, text, expires_at_ms FROM drafts"
            " WHERE handle = ? AND subject = ? AND tenant = ? AND expires_at_ms > ?",
            (handle, owner.subject, owner.tenant, self._clock()),
        ).fetchone()
        if row is None:
            raise UnknownHandle("unknown or expired draft handle")
        version, text, expires_at_ms = row
        return Draft(handle, owner, version, text, expires_at_ms)

    def save(self, owner: Principal, handle: str, text: str, *, expected_version: int) -> Draft:
        """Replace the text if the draft is still at expected_version; the version goes up by one.

        Raises UnknownHandle exactly as get() does, before the version is looked at. If another
        save got there first, raises VersionConflict carrying the version now stored, and changes
        nothing.
        """
        current = self.get(owner, handle)
        with self._db:
            updated = self._db.execute(
                "UPDATE drafts SET text = ?, version = ? WHERE handle = ? AND version = ?",
                (text, expected_version + 1, handle, expected_version),
            ).rowcount
        if updated != 1:
            raise VersionConflict(current.version)
        return Draft(handle, owner, expected_version + 1, text, current.expires_at_ms)

    def close(self) -> None:
        self._db.close()
