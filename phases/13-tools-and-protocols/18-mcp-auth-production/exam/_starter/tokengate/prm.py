"""RFC 9728 protected-resource metadata, and the challenges a refusal carries."""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

from .outcome import Outcome


@dataclass(frozen=True)
class ProtectedResource:
    """This MCP server's canonical resource URL and the authorization servers it trusts."""

    resource: str
    authorization_servers: tuple[str, ...]

    def __post_init__(self) -> None:
        parts = urlsplit(self.resource)
        if parts.scheme != "https" or not parts.netloc or parts.query or parts.fragment:
            raise ValueError("the resource is an absolute HTTPS URL without query or fragment")
        if not self.authorization_servers:
            raise ValueError("authorization_servers names at least one issuer")

    @property
    def metadata_url(self) -> str:
        """Where the metadata is served. The well-known segment goes before the resource's path."""
        parts = urlsplit(self.resource)
        path = "" if parts.path in ("", "/") else parts.path
        return f"https://{parts.netloc}/.well-known/oauth-protected-resource{path}"

    def document(self) -> dict:
        return {
            "resource": self.resource,
            "authorization_servers": list(self.authorization_servers),
            "bearer_methods_supported": ["header"],
        }

    def refuse(self, status: int, reason: str, *, scope: str | None = None, health: str = "ok") -> Outcome:
        """An authorization refusal and its WWW-Authenticate challenge.

        401: Bearer error="invalid_token", error_description="<reason>", resource_metadata="<url>"
        403: Bearer error="insufficient_scope", scope="<scope>", resource_metadata="<url>"
        """
        if status == 403:
            params = f'error="insufficient_scope", scope="{scope}"'
        else:
            params = f'error="invalid_token", error_description="{reason}"'
        challenge = f'Bearer {params}, resource_metadata="{self.metadata_url}"'
        return Outcome("refuse", status, reason, health, challenge)
