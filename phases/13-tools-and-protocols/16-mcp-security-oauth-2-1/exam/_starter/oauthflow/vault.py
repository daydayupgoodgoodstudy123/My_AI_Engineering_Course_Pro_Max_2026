"""Issuer-bound credentials in one JSON snapshot file."""
from __future__ import annotations

import json
import os
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
        # TODO: load the snapshot, if the file exists

    def put_client(self, record: ClientRecord) -> None:
        """Store the client record of record.issuer, replacing an earlier one."""
        raise NotImplementedError

    def client(self, issuer: str) -> ClientRecord | None:
        """The client record of exactly this issuer, or None."""
        raise NotImplementedError

    def put_token(self, record: TokenRecord) -> None:
        """Store a token record under (record.issuer, record.resource), replacing an earlier one."""
        raise NotImplementedError

    def token(self, issuer: str, resource: str) -> TokenRecord | None:
        """The token record of exactly this (issuer, resource), or None."""
        raise NotImplementedError

    def rotate(self, issuer: str, resource: str, presented: str, fresh: TokenRecord) -> None:
        """Record a refresh of (issuer, resource): presented was sent, fresh is what came back.

        presented must be the current refresh token of that record. A refresh token that an
        earlier rotate() replaced raises RefreshReuse and drops the (issuer, resource) record,
        because its chain can no longer be trusted; any other value raises ValueError. fresh then
        replaces the record. When the server issued a new refresh token, presented is remembered as
        used; when it did not (fresh.refresh_token is None, or presented again), presented stays the
        current one.
        """
        raise NotImplementedError
