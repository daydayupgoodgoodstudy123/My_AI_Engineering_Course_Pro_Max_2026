"""Canonical digests: what local integrity checks and an external attestation bind."""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict

SHA256 = re.compile(r"sha256:[0-9a-f]{64}")


def bytes_digest(data: bytes) -> str:
    """"sha256:" and the lowercase hex SHA-256 of data."""
    return "sha256:" + hashlib.sha256(data).hexdigest()


def canonical_json(value: object) -> bytes:
    """UTF-8 JSON with sorted keys and no whitespace. NaN and infinity are refused."""
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False)
    return text.encode("utf-8")


def canonical_digest(value: object) -> str:
    return bytes_digest(canonical_json(value))


def observations_digest(observations: Mapping[str, Sequence[object]]) -> str:
    """One digest over raw run observations (dataclasses): every field of every run, in run order."""
    return canonical_digest({case_id: [asdict(run) for run in runs] for case_id, runs in observations.items()})
