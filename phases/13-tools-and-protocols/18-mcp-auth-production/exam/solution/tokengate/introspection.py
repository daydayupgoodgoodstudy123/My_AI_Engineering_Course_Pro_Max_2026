"""A cache of RFC 7662 introspection results, shared by the server's replicas through SQLite."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable

SCHEMA = """
CREATE TABLE IF NOT EXISTS introspection (
    issuer TEXT NOT NULL,
    token_sha256 TEXT NOT NULL,
    resource TEXT NOT NULL,
    response TEXT NOT NULL,
    expires_at REAL NOT NULL,
    PRIMARY KEY (issuer, token_sha256, resource)
)
"""


class IntrospectionCache:
    """Introspection results for opaque tokens, one SQLite file shared by every replica.

    Entries are keyed by (issuer, SHA-256 hex digest of the token's UTF-8 bytes, resource).
    The token itself is never stored, in any column, and an entry for one issuer or resource
    never answers for another.

    A positive response ("active": true) is served until the earliest of its exp (when it
    has one), now + max_age (the issuer's cache guidance, when given) and now +
    revocation_window. Any other response is negative and is served for negative_ttl
    seconds. An entry is live while now is before its expiry; one that would expire at or
    before now is not stored. Storing replaces whatever the key held. Time comes from clock.
    """

    def __init__(
        self,
        path: str = ":memory:",
        *,
        clock: Callable[[], float],
        revocation_window: float,
        negative_ttl: float,
    ) -> None:
        self.clock = clock
        self.revocation_window = revocation_window
        self.negative_ttl = negative_ttl
        self._db = sqlite3.connect(path, isolation_level=None)  # autocommit: each statement commits
        self._db.execute(SCHEMA)

    def put(
        self, issuer: str, token: str, resource: str, response: dict, *, max_age: float | None = None
    ) -> float | None:
        """Store one introspection response. Return when the entry expires, or None if it is not stored."""
        now = self.clock()
        if response.get("active") is True:
            ends = [now + self.revocation_window]
            if max_age is not None:
                ends.append(now + max_age)
            exp = response.get("exp")
            if isinstance(exp, (int, float)) and not isinstance(exp, bool):
                ends.append(exp)
            expires_at = min(ends)
        else:
            expires_at = now + self.negative_ttl
        key = (issuer, _digest(token), resource)
        if expires_at <= now:
            self._db.execute(
                "DELETE FROM introspection WHERE issuer = ? AND token_sha256 = ? AND resource = ?", key
            )
            return None
        self._db.execute(
            "INSERT OR REPLACE INTO introspection (issuer, token_sha256, resource, response, expires_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (*key, json.dumps(response), expires_at),
        )
        return expires_at

    def get(self, issuer: str, token: str, resource: str) -> dict | None:
        """The live entry's response, exactly as it was stored, or None."""
        row = self._db.execute(
            "SELECT response FROM introspection"
            " WHERE issuer = ? AND token_sha256 = ? AND resource = ? AND expires_at > ?",
            (issuer, _digest(token), resource, self.clock()),
        ).fetchone()
        return None if row is None else json.loads(row[0])

    def lookup(
        self,
        issuer: str,
        token: str,
        resource: str,
        introspect: Callable[[], dict],
        *,
        max_age: float | None = None,
    ) -> dict:
        """Read through the cache: the live entry, or else call introspect() once and store its answer.

        If introspect() raises, the exception propagates and nothing is stored.
        """
        cached = self.get(issuer, token, resource)
        if cached is not None:
            return cached
        response = introspect()
        self.put(issuer, token, resource, response, max_age=max_age)
        return response

    def close(self) -> None:
        self._db.close()


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
