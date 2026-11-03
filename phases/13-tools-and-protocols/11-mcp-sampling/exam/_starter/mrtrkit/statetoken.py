"""requestState tokens, version 1: a binary layout with a key id, so the secret can rotate.

The client carries this token between MRTR rounds and must echo it byte for byte. Layout:

    offset   size  field
    0        1     version, always 1
    1        1     key id (0-255): the keyring entry that signed the token
    2        8     expiresAt: Unix seconds, unsigned, big-endian
    10       4     payload length in bytes, unsigned, big-endian
    14       n     payload: the state as canonical JSON, UTF-8
    14 + n   32    HMAC-SHA256 of bytes 0 to 13 + n, with the key for the key id

The token is the whole byte string in base64url with the trailing "=" padding removed.
Canonical JSON here sorts keys, has no spaces, writes non-ASCII characters as themselves (no
\\u escapes), and has no NaN or Infinity.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

VERSION = 1


class StateError(ValueError):
    """A requestState that must not be trusted: malformed, altered, unknown, or expired."""


@dataclass(frozen=True)
class Keyring:
    """HMAC keys by key id. New tokens are signed with keys[current]; older keys still verify."""

    keys: dict[int, bytes]
    current: int


def seal_state(state: dict[str, Any], keyring: Keyring, expires_at: int) -> str:
    """Encode state as a version 1 token, signed with the keyring's current key.

    ValueError if the state has no canonical JSON form (NaN or Infinity).
    """
    raise NotImplementedError


def open_state(token: str, keyring: Keyring, now: int) -> dict[str, Any]:
    """Check a version 1 token and return its state exactly as it was sealed.

    StateError for anything else: text that is not base64url, a byte string that is too short,
    too long or altered anywhere, an unknown version or key id, or now past expiresAt. A token
    is still valid at its expiresAt second.
    """
    raise NotImplementedError
