"""Integrity-protected requestState.

The server signs everything a retry needs, so any server object that holds the secret
can process the retry. The state is signed, not encrypted: never put a secret in it.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
from typing import Any

from .protocol import McpError

DEMO_SECRET = b"scopegate-demo-secret-change-in-production"


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def arguments_digest(arguments: dict[str, Any]) -> str:
    encoded = json.dumps(arguments, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def seal_state(
    secret: bytes,
    *,
    principal: str,
    arguments: dict[str, Any],
    expires_at: float,
    **fields: Any,
) -> str:
    """Sign fields together with the principal, tools/call, these exact arguments and an expiry."""
    payload = {
        **fields,
        "principal": principal,
        "method": "tools/call",
        "argumentsDigest": arguments_digest(arguments),
        "expiresAt": expires_at,
    }
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    signature = hmac.new(secret, body, hashlib.sha256).digest()
    return f"{_b64(body)}.{_b64(signature)}"


def open_state(
    secret: bytes,
    token: Any,
    *,
    principal: str,
    arguments: dict[str, Any],
    now: float,
) -> dict[str, Any]:
    """Verify a token made by seal_state and return its payload.

    Every problem raises McpError(-32602, ...): a token that is not a string or does
    not verify, another principal, other arguments, or an expiry at or before now.
    """
    if not isinstance(token, str):
        raise McpError(-32602, "requestState must be a string")
    try:
        body_part, signature_part = token.split(".", 1)
        body = _unb64(body_part)
        supplied = _unb64(signature_part)
    except (ValueError, binascii.Error) as exc:
        raise McpError(-32602, "invalid requestState encoding") from exc
    expected = hmac.new(secret, body, hashlib.sha256).digest()
    if not hmac.compare_digest(supplied, expected):
        raise McpError(-32602, "requestState integrity check failed")
    state = json.loads(body)
    if state.get("principal") != principal:
        raise McpError(-32602, "requestState principal mismatch")
    if state.get("method") != "tools/call":
        raise McpError(-32602, "requestState method mismatch")
    if state.get("argumentsDigest") != arguments_digest(arguments):
        raise McpError(-32602, "requestState arguments mismatch")
    expires_at = state.get("expiresAt")
    if type(expires_at) not in (int, float):
        raise McpError(-32602, "invalid requestState expiry")
    if expires_at <= now:
        raise McpError(-32602, "requestState expired")
    return state
