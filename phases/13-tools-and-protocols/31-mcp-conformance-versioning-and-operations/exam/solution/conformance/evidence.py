"""Evidence helpers: canonical JSON, SHA-256 digests and redaction."""
from __future__ import annotations

import hashlib
import json
from typing import Any

REDACTED = "[REDACTED]"

# Canonical forms (see canonical_field_name) of the keys whose values never leave memory.
SECRET_KEYS = frozenset(
    {
        "authorization",
        "proxyauthorization",
        "cookie",
        "setcookie",
        "xapikey",
        "apikey",
        "accesstoken",
        "refreshtoken",
        "registrationaccesstoken",
        "token",
        "clientsecret",
        "secret",
        "password",
    }
)


def canonical_json(value: Any) -> str:
    """Sorted keys, no spaces, ASCII only: the same value always gives the same text."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value: Any) -> str:
    """SHA-256 hex digest of the canonical JSON of value."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def is_sha256_digest(value: Any) -> bool:
    """True for a string of exactly 64 hex digits."""
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdefABCDEF" for character in value)
    )


def canonical_field_name(key: str) -> str:
    """Case-fold a key and keep only its letters and digits.

    X-Api-Key, x_api_key, x.api.key and xApiKey all become xapikey.
    """
    return "".join(character for character in key.casefold() if character.isalnum())


def redact(value: Any) -> Any:
    """Return a copy of value with every secret replaced by REDACTED.

    A member is secret when its key, in canonical form, is in SECRET_KEYS. Its whole value is
    replaced, at any depth, inside objects and inside lists. Every other key, and every value
    that is not under a secret key, is kept as it is.
    """
    if isinstance(value, dict):
        return {
            key: REDACTED if canonical_field_name(key) in SECRET_KEYS else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value
