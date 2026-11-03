"""Compact JWS helpers for HS256 JWT access tokens.

HS256 keeps the package in the standard library. Production issuers sign with RS256 or EdDSA
and publish only public keys; the validation around the signature check is the same.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re

_B64URL = re.compile(r"[A-Za-z0-9_-]*")


class TokenError(ValueError):
    """The bearer token is not a well-formed compact JWT."""


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def b64url_decode(text: str) -> bytes:
    if not _B64URL.fullmatch(text) or len(text) % 4 == 1:
        raise TokenError("segment is not unpadded base64url")
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _segment(value: dict) -> str:
    return b64url(json.dumps(value, separators=(",", ":")).encode("utf-8"))


def encode(header: dict, claims: dict, secret: bytes | None) -> str:
    """Serialize and sign a JWT. secret None leaves the signature empty, as alg "none" does."""
    signing_input = f"{_segment(header)}.{_segment(claims)}"
    if secret is None:
        signature = b""
    else:
        signature = hmac.new(secret, signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{b64url(signature)}"


def parse(token: object) -> tuple[dict, dict]:
    """Decode a compact JWT without verifying it and return (header, claims).

    Raises TokenError unless the token is three base64url segments and the first two are
    JSON objects.
    """
    if not isinstance(token, str):
        raise TokenError("a bearer token is a string")
    parts = token.split(".")
    if len(parts) != 3:
        raise TokenError("a compact JWT has three segments")
    try:
        header = json.loads(b64url_decode(parts[0]))
        claims = json.loads(b64url_decode(parts[1]))
    except ValueError as exc:
        raise TokenError("header and claims must be JSON") from exc
    b64url_decode(parts[2])
    if not isinstance(header, dict) or not isinstance(claims, dict):
        raise TokenError("header and claims must be JSON objects")
    return header, claims


def verify(token: str, jwk: dict) -> bool:
    """True when the token's HS256 signature was made with this oct key. Call after parse."""
    signing_input, _, signature = token.rpartition(".")
    expected = hmac.new(b64url_decode(jwk["k"]), signing_input.encode("ascii"), hashlib.sha256).digest()
    return hmac.compare_digest(expected, b64url_decode(signature))
