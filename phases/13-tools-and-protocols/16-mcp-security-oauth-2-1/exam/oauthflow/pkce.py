"""PKCE for the authorization code flow: a high-entropy verifier and its S256 challenge."""
from __future__ import annotations

import base64
import hashlib
import secrets


def s256(verifier: str) -> str:
    """The S256 code_challenge of a code_verifier: BASE64URL(SHA-256(ASCII(verifier))) without '=' padding."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii")


def pkce_pair() -> tuple[str, str]:
    """A fresh (code_verifier, code_challenge) pair. The verifier is 256 random bits as 43 base64url characters."""
    verifier = secrets.token_urlsafe(32)
    return verifier, s256(verifier)
