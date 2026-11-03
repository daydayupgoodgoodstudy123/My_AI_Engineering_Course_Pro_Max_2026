"""Redirect URI rules for deprecated RFC 7591 dynamic client registration (DCR)."""
from __future__ import annotations


def redirect_uri_fits(uri: object, application_type: str) -> bool:
    """Whether uri may be registered as a redirect URI for a client of this application_type.

    Every redirect URI is a string with no whitespace and no control characters anywhere. It is
    absolute (it has an RFC 3986 scheme), it has no fragment (no "#" at all), and its authority,
    when it has one, carries no userinfo (no "@") and only a port of 1 to 5 ASCII digits no
    greater than 65535.

    web: https with a non-empty host.
    native: https with a non-empty host; http whose host is exactly localhost, 127.0.0.1 or
    [::1], on any port; or a private-use scheme of two or more dot-separated labels, each made
    of ASCII letters, digits and hyphens, starting and ending with a letter or digit
    (com.example.app:/oauth2redirect).

    Schemes and hosts compare case-insensitively; a query is allowed. Any application_type other
    than "native" or "web" raises ValueError.
    """
    raise NotImplementedError


def registration_error(body: dict) -> str | None:
    """Check a deprecated RFC 7591 registration request. Return its RFC 7591 error code, or None.

    DCR requires application_type, and it must be "native" or "web": anything else, missing
    included, is "invalid_client_metadata". redirect_uris must then be a non-empty list whose
    every entry fits that application_type: otherwise "invalid_redirect_uri".
    """
    raise NotImplementedError
