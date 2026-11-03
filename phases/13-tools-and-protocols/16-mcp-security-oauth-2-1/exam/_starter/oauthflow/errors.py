"""Errors raised by oauthflow."""
from __future__ import annotations


class OAuthFlowError(Exception):
    """Base class of every oauthflow error."""


class HttpError(OAuthFlowError):
    """A metadata fetch got an answer other than 200."""

    def __init__(self, status: int, url: str) -> None:
        super().__init__(f"{status} for {url}")
        self.status = status
        self.url = url


class DiscoveryError(OAuthFlowError):
    """Protected-resource or authorization-server metadata cannot be used."""


class StateMismatch(OAuthFlowError):
    """An authorization response belongs to another flow."""


class IssuerMismatch(OAuthFlowError):
    """An authorization response names another issuer (RFC 9207)."""


class AuthorizationError(OAuthFlowError):
    """The authorization server refused a request, or the user declined."""

    def __init__(self, error: str, description: str = "") -> None:
        super().__init__(f"{error}: {description}" if description else error)
        self.error = error
        self.description = description


class TokenError(AuthorizationError):
    """The token endpoint answered with an error."""


class McpError(OAuthFlowError):
    """An MCP request got an HTTP status other than 200."""

    def __init__(self, status: int, headers: dict[str, str], body: dict | None) -> None:
        challenge = next((v for k, v in headers.items() if k.lower() == "www-authenticate"), "")
        super().__init__(f"HTTP {status}" + (f" ({challenge})" if challenge else ""))
        self.status = status
        self.headers = headers
        self.body = body


class NeedClientInfo(OAuthFlowError):
    """No way to identify this client to an issuer: the user has to supply client information."""


class RefreshReuse(OAuthFlowError):
    """A refresh token that was already rotated away was presented again."""


class FetchBlocked(OAuthFlowError):
    """A metadata fetch broke one of the fetch rules."""


class CimdInvalid(OAuthFlowError):
    """A Client ID Metadata Document failed validation."""
