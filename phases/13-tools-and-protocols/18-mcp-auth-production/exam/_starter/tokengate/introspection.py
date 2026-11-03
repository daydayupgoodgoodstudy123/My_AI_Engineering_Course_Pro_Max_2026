"""A cache of RFC 7662 introspection results, shared by the server's replicas through SQLite."""
from __future__ import annotations

import sqlite3
from collections.abc import Callable


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
        # TODO: create the schema

    def put(
        self, issuer: str, token: str, resource: str, response: dict, *, max_age: float | None = None
    ) -> float | None:
        """Store one introspection response. Return when the entry expires, or None if it is not stored."""
        raise NotImplementedError

    def get(self, issuer: str, token: str, resource: str) -> dict | None:
        """The live entry's response, exactly as it was stored, or None."""
        raise NotImplementedError

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
        raise NotImplementedError

    def close(self) -> None:
        self._db.close()
