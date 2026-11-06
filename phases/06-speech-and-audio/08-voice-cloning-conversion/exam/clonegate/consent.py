"""Signed consents to clone a speaker's voice, stored in SQLite."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Consent:
    consent_id: int
    speaker: str
    purposes: frozenset[str]
    granted_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None

    def allows(self, purpose: str, at: datetime) -> bool:
        """True when purpose is in scope and at is in [granted_at, expires_at) and before any revocation.

        A naive at raises ValueError.
        """
        raise NotImplementedError


class ConsentRegistry:
    """Consents to clone a speaker's voice.

    Ids are small integers issued in order (1, 2, ...) because they travel in the 16-bit
    watermark payload. Times must be timezone-aware (naive ones raise ValueError) and come
    back exactly as given, offset included: a consent signed on 22 April in Mumbai stays
    signed on 22 April.
    """

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        # TODO: create the schema

    def grant(self, speaker: str, purposes: set[str], granted_at: datetime, expires_at: datetime) -> Consent:
        """Record a consent and return it. It must expire after it is granted, and name a purpose."""
        raise NotImplementedError

    def get(self, consent_id: int) -> Consent:
        """The stored consent. Unknown ids raise KeyError."""
        raise NotImplementedError

    def revoke(self, consent_id: int, at: datetime) -> Consent:
        """Revoke a consent from at onwards. Revocation is permanent: revoking again keeps the first time."""
        raise NotImplementedError

    def active(self, speaker: str, purpose: str, at: datetime) -> list[Consent]:
        """The speaker's consents that allow purpose at time at, in the order they were granted."""
        raise NotImplementedError

    def close(self) -> None:
        self._db.close()
