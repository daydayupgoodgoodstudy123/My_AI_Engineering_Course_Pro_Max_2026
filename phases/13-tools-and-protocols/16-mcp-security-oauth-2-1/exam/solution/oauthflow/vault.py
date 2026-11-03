"""Issuer-bound credentials in one JSON snapshot file."""
from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import json
import os
import tempfile
from pathlib import Path

from .errors import RefreshReuse
from .model import ClientRecord, TokenRecord


class CredentialVault:
    """Client records keyed by the exact issuer and token records by (issuer, resource), in one JSON file.

    Issuers and resources are exact strings: https://auth.example.com and https://auth.example.com/
    are two issuers, and nothing stored for one is ever returned for the other.

    Every change is in the file before the method returns, and a vault opened later on the same
    path reads back exactly what was stored. The file holds secrets, so it is created with mode
    0600 and never chmod-ed afterwards: a file that is readable even for a moment can be opened by
    another user, who keeps reading through that handle after the mode changes.

    A refresh token that rotate() replaced stays remembered as used, in the file, so presenting it
    again is detected as reuse.
    """

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)
        try:
            snapshot = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            snapshot = {}
        self._clients: dict[str, dict] = snapshot.get("clients", {})
        self._tokens: dict[str, dict[str, dict]] = snapshot.get("tokens", {})
        self._used: dict[str, dict[str, list[str]]] = snapshot.get("used_refresh_tokens", {})

    def put_client(self, record: ClientRecord) -> None:
        """Store the client record of record.issuer, replacing an earlier one."""
        self._clients[record.issuer] = dataclasses.asdict(record)
        self._save()

    def client(self, issuer: str) -> ClientRecord | None:
        """The client record of exactly this issuer, or None."""
        data = self._clients.get(issuer)
        return None if data is None else ClientRecord(**data)

    def put_token(self, record: TokenRecord) -> None:
        """Store a token record under (record.issuer, record.resource), replacing an earlier one."""
        self._tokens.setdefault(record.issuer, {})[record.resource] = dataclasses.asdict(record)
        self._save()

    def token(self, issuer: str, resource: str) -> TokenRecord | None:
        """The token record of exactly this (issuer, resource), or None."""
        data = self._tokens.get(issuer, {}).get(resource)
        return None if data is None else TokenRecord(**data)

    def rotate(self, issuer: str, resource: str, presented: str, fresh: TokenRecord) -> None:
        """Record a refresh of (issuer, resource): presented was sent, fresh is what came back.

        presented must be the current refresh token of that record. A refresh token that an
        earlier rotate() replaced raises RefreshReuse and drops the (issuer, resource) record,
        because its chain can no longer be trusted; any other value raises ValueError. fresh then
        replaces the record. When the server issued a new refresh token, presented is remembered as
        used; when it did not (fresh.refresh_token is None, or presented again), presented stays the
        current one.
        """
        if (fresh.issuer, fresh.resource) != (issuer, resource):
            raise ValueError("fresh belongs to another (issuer, resource)")
        used = self._used.get(issuer, {}).get(resource, [])
        if _fingerprint(presented) in used:
            self._tokens.get(issuer, {}).pop(resource, None)
            self._save()
            raise RefreshReuse(f"a rotated refresh token of {resource} at {issuer} came back")
        current = self.token(issuer, resource)
        if current is None or current.refresh_token != presented:
            raise ValueError("presented is not the current refresh token of this (issuer, resource)")
        if fresh.refresh_token is None:
            fresh = dataclasses.replace(fresh, refresh_token=presented)
        elif fresh.refresh_token != presented:
            self._used.setdefault(issuer, {}).setdefault(resource, []).append(_fingerprint(presented))
        self._tokens[issuer][resource] = dataclasses.asdict(fresh)
        self._save()

    def _save(self) -> None:
        snapshot = {"clients": self._clients, "tokens": self._tokens, "used_refresh_tokens": self._used}
        data = json.dumps(snapshot, indent=2, sort_keys=True).encode("utf-8")
        # mkstemp creates the file with mode 0600; os.replace keeps that mode
        handle, temp = tempfile.mkstemp(prefix=".vault-", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(handle, "wb") as out:
                out.write(data)
                out.flush()
                os.fsync(out.fileno())
            os.replace(temp, self.path)
        except BaseException:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(temp)
            raise


def _fingerprint(refresh_token: str) -> str:
    """Used refresh tokens are remembered by their SHA-256, not in clear."""
    return hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()
