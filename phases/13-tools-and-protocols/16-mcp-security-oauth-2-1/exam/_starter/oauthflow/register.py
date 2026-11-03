"""Which client id this client presents to each authorization server."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from .errors import NeedClientInfo
from .model import ClientRecord
from .net import Network
from .vault import CredentialVault

LOOPBACK_HOSTS = ("127.0.0.1", "::1", "localhost")


class FixedClientId:
    """Presents one client id to every issuer.

    Meant for a Client ID Metadata Document URL: the client hosts that document itself, so no
    issuer minted the id, and the same URL works with every server that supports CIMD.
    """

    def __init__(self, client_id: str) -> None:
        self.client_id = client_id

    def client_id_for(self, issuer: str, metadata: Mapping[str, Any]) -> str:
        return self.client_id


def dcr_metadata(client_name: str, redirect_uri: str) -> dict[str, Any]:
    """Dynamic Client Registration metadata for this client.

    DCR declares application_type: native for desktop, mobile, command-line and loopback clients,
    web only for a remotely hosted client with a remote HTTPS redirect. Left out, an OpenID Connect
    registration can default to web and refuse a loopback redirect.
    """
    parts = urlsplit(redirect_uri)
    remote_https = parts.scheme == "https" and parts.hostname not in LOOPBACK_HOSTS
    return {
        "client_name": client_name,
        "application_type": "web" if remote_https else "native",
        "redirect_uris": [redirect_uri],
        "grant_types": ["authorization_code"],
        "response_types": ["code"],
    }


class Registrar:
    """Picks the client id for each issuer, in the lesson's registration priority.

    1. A client pre-registered with this exact issuer: a ClientRecord with method "preregistered"
       in the vault.
    2. The Client ID Metadata Document URL (cimd_url), when the server's metadata has
       client_id_metadata_document_supported: true. The same URL works with every such issuer.
    3. Dynamic Client Registration, only when allow_dcr is set and the metadata has a
       registration_endpoint: this issuer's earlier DCR client from the vault, or a new
       registration (dcr_metadata), kept in the vault under the exact issuer as a ClientRecord
       with method "dcr" and the answer's client_secret and registration_access_token. A DCR
       client id is never offered to another issuer.
    4. Otherwise NeedClientInfo: the user has to supply client information.

    Issuers are exact strings. A server that later rejects the CIMD client id has produced an
    error, not a reason to fall back to DCR.
    """

    def __init__(
        self,
        net: Network,
        vault: CredentialVault,
        *,
        client_name: str,
        redirect_uri: str,
        cimd_url: str | None = None,
        allow_dcr: bool = False,
    ) -> None:
        self.net = net
        self.vault = vault
        self.client_name = client_name
        self.redirect_uri = redirect_uri
        self.cimd_url = cimd_url
        self.allow_dcr = allow_dcr

    def client_id_for(self, issuer: str, metadata: Mapping[str, Any]) -> str:
        """The client id to present to issuer, whose metadata is given."""
        raise NotImplementedError
