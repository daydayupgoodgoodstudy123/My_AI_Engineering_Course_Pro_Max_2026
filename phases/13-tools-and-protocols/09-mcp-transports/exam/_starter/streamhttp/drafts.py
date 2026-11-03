"""Drafts that any replica can load, kept in one SQLite file that every replica opens.

Request A may reach replica 1 and request B replica 2, so a draft never lives only in one
replica's memory. It is stored under a server-minted handle, which goes back to the client in an
ordinary tool result and comes in again as an ordinary tool argument.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass

from .protocol import Principal

DEFAULT_TTL_MS = 15 * 60 * 1000


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
        # TODO: create the schema

    def create(self, owner: Principal, text: str) -> Draft:
        """Store a new draft, version 1, under a fresh handle, and return it.

        Handles are opaque and unguessable: at least 128 random bits from the secrets module, so
        no two replicas ever mint the same one.
        """
        raise NotImplementedError

    def get(self, owner: Principal, handle: str) -> Draft:
        """The draft as last saved through any replica.

        A handle that was never issued, has expired, or belongs to another subject or tenant
        raises the same UnknownHandle, so the caller cannot tell these apart. A draft is live
        while clock() is before its expires_at_ms.
        """
        raise NotImplementedError

    def save(self, owner: Principal, handle: str, text: str, *, expected_version: int) -> Draft:
        """Replace the text if the draft is still at expected_version; the version goes up by one.

        Raises UnknownHandle exactly as get() does, before the version is looked at. If another
        save got there first, raises VersionConflict carrying the version now stored, and changes
        nothing.
        """
        raise NotImplementedError

    def close(self) -> None:
        self._db.close()
