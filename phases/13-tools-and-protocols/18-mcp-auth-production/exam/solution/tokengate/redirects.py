"""Redirect URI rules for deprecated RFC 7591 dynamic client registration (DCR)."""
from __future__ import annotations

import re

LOOPBACK_HOSTS = ("localhost", "127.0.0.1", "::1")
_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.\-]*")
_LABEL = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9\-]*[A-Za-z0-9])?")
_PORT = re.compile(r"[0-9]{1,5}")


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
    if application_type not in ("native", "web"):
        raise ValueError(f"application_type must be native or web, not {application_type!r}")
    if not isinstance(uri, str) or any(ch.isspace() or ord(ch) < 0x20 or ord(ch) == 0x7F for ch in uri):
        return False
    if "#" in uri:
        return False
    scheme, colon, rest = uri.partition(":")
    if not colon or not _SCHEME.fullmatch(scheme):
        return False
    scheme = scheme.lower()
    host = None
    if rest.startswith("//"):
        host = _host(re.split(r"[/?]", rest[2:], maxsplit=1)[0])
        if host is None:
            return False
    if scheme == "https":
        return bool(host)
    if application_type == "web":
        return False
    if scheme == "http":
        return host in LOOPBACK_HOSTS
    labels = scheme.split(".")
    return len(labels) >= 2 and all(_LABEL.fullmatch(label) for label in labels)


def _host(authority: str) -> str | None:
    """The authority's host, lowercased, or None when it has userinfo or a malformed port."""
    if "@" in authority:
        return None
    if authority.startswith("["):
        end = authority.find("]")
        if end == -1:
            return None
        host, after = authority[1:end], authority[end + 1 :]
        if after and not after.startswith(":"):
            return None
        port = after[1:] if after else None
    else:
        host, colon, port = authority.partition(":")
        if not colon:
            port = None
    if port is not None and not (_PORT.fullmatch(port) and int(port) <= 65535):
        return None
    return host.lower()


def registration_error(body: dict) -> str | None:
    """Check a deprecated RFC 7591 registration request. Return its RFC 7591 error code, or None.

    DCR requires application_type, and it must be "native" or "web": anything else, missing
    included, is "invalid_client_metadata". redirect_uris must then be a non-empty list whose
    every entry fits that application_type: otherwise "invalid_redirect_uri".
    """
    application_type = body.get("application_type")
    if application_type not in ("native", "web"):
        return "invalid_client_metadata"
    uris = body.get("redirect_uris")
    if not isinstance(uris, list) or not uris:
        return "invalid_redirect_uri"
    if not all(redirect_uri_fits(uri, application_type) for uri in uris):
        return "invalid_redirect_uri"
    return None
