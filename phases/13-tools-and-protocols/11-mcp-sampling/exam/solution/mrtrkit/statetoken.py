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

import base64
import hashlib
import hmac
import json
import re
import struct
from dataclasses import dataclass
from typing import Any

VERSION = 1
HEADER = struct.Struct(">BBQI")
MAC_SIZE = 32
BASE64URL = re.compile(r"[A-Za-z0-9_-]*")


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
    payload = json.dumps(
        state, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    body = HEADER.pack(VERSION, keyring.current, expires_at, len(payload)) + payload
    mac = hmac.new(keyring.keys[keyring.current], body, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(body + mac).decode("ascii").rstrip("=")


def open_state(token: str, keyring: Keyring, now: int) -> dict[str, Any]:
    """Check a version 1 token and return its state exactly as it was sealed.

    StateError for anything else: text that is not base64url, a byte string that is too short,
    too long or altered anywhere, an unknown version or key id, or now past expiresAt. A token
    is still valid at its expiresAt second.
    """
    if not isinstance(token, str) or not BASE64URL.fullmatch(token):
        raise StateError("requestState is not unpadded base64url text")
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    except ValueError as exc:
        raise StateError("requestState is not base64url") from exc
    if len(raw) < HEADER.size + MAC_SIZE:
        raise StateError("requestState is too short")
    version, key_id, expires_at, length = HEADER.unpack_from(raw)
    if version != VERSION:
        raise StateError(f"unknown requestState version {version}")
    key = keyring.keys.get(key_id)
    if key is None:
        raise StateError(f"unknown key id {key_id}")
    if len(raw) != HEADER.size + length + MAC_SIZE:
        raise StateError("requestState length does not match its header")
    body, mac = raw[:-MAC_SIZE], raw[-MAC_SIZE:]
    if not hmac.compare_digest(mac, hmac.new(key, body, hashlib.sha256).digest()):
        raise StateError("requestState signature does not match")
    if now > expires_at:
        raise StateError("requestState expired")
    try:
        return json.loads(body[HEADER.size :].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StateError("requestState payload is not JSON") from exc
