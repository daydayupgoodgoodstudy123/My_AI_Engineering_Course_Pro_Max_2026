"""Signed override entries: "The override is a signed change, not an agent decision."

An entry is the six FIELDS plus "signature", the HMAC-SHA256 of the other fields' canonical JSON
under the team's override secret, cut to its first 32 hex digits. The secret lives with the humans
who can approve overrides, not in the agent's environment.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time

FIELDS = ("task_id", "finding_code", "reason", "user_id", "head_commit", "ts")


def canonical(fields: dict) -> bytes:
    """The bytes a signature covers: compact JSON with sorted keys (json.dumps defaults otherwise)."""
    return json.dumps(fields, sort_keys=True, separators=(",", ":")).encode()


def _mac(body: bytes, secret: bytes) -> str:
    if not secret:
        raise ValueError("no override secret: refusing to sign or check overrides (fail closed)")
    return hmac.new(secret, body, hashlib.sha256).hexdigest()[:32]


def sign(fields: dict, secret: bytes) -> str:
    """HMAC-SHA256 of canonical(fields) under secret, as its first 32 hex digits. An empty secret is refused."""
    return _mac(canonical(fields), secret)


def verify_signature(entry: dict, secret: bytes) -> bool:
    """True when entry["signature"] is sign() of every other field of entry.

    A missing or malformed signature, or a field that json cannot encode, is simply not valid.
    """
    signature = entry.get("signature")
    if not isinstance(signature, str) or not signature.isascii():
        return False
    try:
        body = canonical({k: v for k, v in entry.items() if k != "signature"})
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(_mac(body, secret), signature)


def make_override(
    task_id: str,
    finding_code: str,
    reason: str,
    user_id: str,
    head_commit: str,
    *,
    secret: bytes,
    ts: float | None = None,
) -> dict:
    """A signed override entry: the six FIELDS, and a signature over all six.

    ts is when the human signed off (time.time() unless given). The five strings must not be blank:
    an override without a reason or a user is not an override.
    """
    values = (task_id, finding_code, reason, user_id, head_commit)
    if not all(isinstance(v, str) and v.strip() for v in values):
        raise ValueError("an override needs task_id, finding_code, reason, user_id and head_commit")
    entry = {
        "task_id": task_id,
        "finding_code": finding_code,
        "reason": reason,
        "user_id": user_id,
        "head_commit": head_commit,
    }
    entry["signature"] = sign(entry, secret)
    entry["ts"] = time.time() if ts is None else ts
    return entry
