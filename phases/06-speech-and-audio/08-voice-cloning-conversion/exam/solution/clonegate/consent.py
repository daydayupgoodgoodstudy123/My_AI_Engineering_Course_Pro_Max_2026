"""Signed consents to clone a speaker's voice, stored in SQLite."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS consents (
    consent_id INTEGER PRIMARY KEY AUTOINCREMENT,
    speaker TEXT NOT NULL,
    purposes TEXT NOT NULL,
    granted_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT
)
"""
COLUMNS = "consent_id, speaker, purposes, granted_at, expires_at, revoked_at"


def aware(moment: datetime) -> datetime:
    """moment itself, or ValueError when it has no time zone."""
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError(f"{moment.isoformat()} has no time zone")
    return moment


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
        aware(at)
        if purpose not in self.purposes or not self.granted_at <= at < self.expires_at:
            return False
        return self.revoked_at is None or at < self.revoked_at


class ConsentRegistry:
    """Consents to clone a speaker's voice.

    Ids are small integers issued in order (1, 2, ...) because they travel in the 16-bit
    watermark payload. Times must be timezone-aware (naive ones raise ValueError) and come
    back exactly as given, offset included: a consent signed on 22 April in Mumbai stays
    signed on 22 April.
    """

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        with self._db:
            self._db.execute(SCHEMA)

    def grant(self, speaker: str, purposes: set[str], granted_at: datetime, expires_at: datetime) -> Consent:
        """Record a consent and return it. It must expire after it is granted, and name a purpose."""
        if not purposes:
            raise ValueError("a consent names at least one purpose")
        if aware(expires_at) <= aware(granted_at):
            raise ValueError("a consent must expire after it is granted")
        with self._db:
            cursor = self._db.execute(
                "INSERT INTO consents (speaker, purposes, granted_at, expires_at) VALUES (?, ?, ?, ?)",
                (speaker, json.dumps(sorted(purposes)), granted_at.isoformat(), expires_at.isoformat()),
            )
        return self.get(cursor.lastrowid)

    def get(self, consent_id: int) -> Consent:
        """The stored consent. Unknown ids raise KeyError."""
        row = self._db.execute(
            f"SELECT {COLUMNS} FROM consents WHERE consent_id = ?", (consent_id,)
        ).fetchone()
        if row is None:
            raise KeyError(consent_id)
        return _to_consent(row)

    def revoke(self, consent_id: int, at: datetime) -> Consent:
        """Revoke a consent from at onwards. Revocation is permanent: revoking again keeps the first time."""
        aware(at)
        if self.get(consent_id).revoked_at is None:
            with self._db:
                self._db.execute(
                    "UPDATE consents SET revoked_at = ? WHERE consent_id = ?", (at.isoformat(), consent_id)
                )
        return self.get(consent_id)

    def active(self, speaker: str, purpose: str, at: datetime) -> list[Consent]:
        """The speaker's consents that allow purpose at time at, in the order they were granted."""
        rows = self._db.execute(
            f"SELECT {COLUMNS} FROM consents WHERE speaker = ? ORDER BY consent_id", (speaker,)
        )
        return [consent for consent in map(_to_consent, rows) if consent.allows(purpose, at)]

    def close(self) -> None:
        self._db.close()


def _to_consent(row: tuple) -> Consent:
    consent_id, speaker, purposes, granted_at, expires_at, revoked_at = row
    return Consent(
        consent_id,
        speaker,
        frozenset(json.loads(purposes)),
        datetime.fromisoformat(granted_at),
        datetime.fromisoformat(expires_at),
        None if revoked_at is None else datetime.fromisoformat(revoked_at),
    )
