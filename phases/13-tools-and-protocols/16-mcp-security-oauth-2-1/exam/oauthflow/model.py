"""Records shared by the client, the vault and the loopback desk."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Discovery:
    """What discovery found for one MCP resource."""

    resource: str
    issuer: str
    resource_metadata: dict
    server_metadata: dict


@dataclass(frozen=True)
class PendingAuth:
    """One authorization request in flight: everything the later steps of the flow need again."""

    issuer: str
    resource: str
    client_id: str
    redirect_uri: str
    scope: str
    state: str
    verifier: str
    authorization_endpoint: str
    token_endpoint: str


@dataclass(frozen=True)
class TokenRecord:
    """An access token and what it is for.

    scope is the granted scope string exactly as the server sent it, and expires_at is in whole
    seconds since the epoch.
    """

    issuer: str
    resource: str
    access_token: str
    scope: str
    expires_at: int
    refresh_token: str | None = None


@dataclass(frozen=True)
class ClientRecord:
    """Enrollment material that one issuer minted: a pre-registered client or a DCR registration."""

    issuer: str
    client_id: str
    method: str  # "preregistered" or "dcr"
    client_secret: str | None = None
    registration_access_token: str | None = None
