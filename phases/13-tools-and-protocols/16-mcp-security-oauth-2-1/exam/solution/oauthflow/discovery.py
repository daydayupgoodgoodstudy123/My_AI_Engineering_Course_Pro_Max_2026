"""Protected-resource discovery (RFC 9728) and authorization-server metadata."""
from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from .errors import DiscoveryError
from .model import Discovery
from .net import Network

RESOURCE_WELL_KNOWN = "/.well-known/oauth-protected-resource"
SERVER_WELL_KNOWN = "/.well-known/oauth-authorization-server"


def protected_resource_metadata_url(resource: str) -> str:
    """The RFC 9728 metadata URL of an MCP resource.

    The well-known path goes between the host and the resource's own path, and that path is kept:
    https://notes.example.com/mcp -> https://notes.example.com/.well-known/oauth-protected-resource/mcp.
    Dropping it would fetch the metadata of whatever resource sits at the root of the origin.
    """
    parts = urlsplit(resource)
    path = "" if parts.path == "/" else parts.path
    return urlunsplit((parts.scheme, parts.netloc, RESOURCE_WELL_KNOWN + path, parts.query, ""))


def authorization_server_metadata_url(issuer: str) -> str:
    """The metadata URL of an issuer.

    https://auth.example.com -> https://auth.example.com/.well-known/oauth-authorization-server
    """
    parts = urlsplit(issuer)
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme, parts.netloc, SERVER_WELL_KNOWN + path, "", ""))


def discover(net: Network, resource: str) -> Discovery:
    """Fetch a resource's protected-resource metadata, then the metadata of its authorization server.

    The resource metadata must name this exact resource. Its first authorization server is used,
    and that server's metadata must name the same issuer, exactly, and support S256 for PKCE.
    """
    resource_metadata = net.get_json(protected_resource_metadata_url(resource))
    if resource_metadata.get("resource") != resource:
        raise DiscoveryError(
            f"the metadata is for {resource_metadata.get('resource')!r}, not {resource!r}"
        )
    servers = resource_metadata.get("authorization_servers") or []
    if not servers:
        raise DiscoveryError(f"{resource} lists no authorization server")
    issuer = servers[0]
    server_metadata = net.get_json(authorization_server_metadata_url(issuer))
    if server_metadata.get("issuer") != issuer:
        raise DiscoveryError(
            f"the server metadata names {server_metadata.get('issuer')!r}, not {issuer!r}"
        )
    if "S256" not in server_metadata.get("code_challenge_methods_supported", []):
        raise DiscoveryError(f"{issuer} does not support S256")
    return Discovery(resource, issuer, resource_metadata, server_metadata)
