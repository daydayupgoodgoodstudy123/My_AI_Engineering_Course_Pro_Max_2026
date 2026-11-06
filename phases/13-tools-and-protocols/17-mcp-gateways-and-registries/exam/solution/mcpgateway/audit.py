"""Where the gateway's audit events go: memory for tests, an append-only JSONL file for real."""
from __future__ import annotations

import copy
from typing import Any

from .audit_io import JsonlAuditSink

SECRET_KEYS = frozenset(
    {
        "authorization",
        "token",
        "access_token",
        "refresh_token",
        "id_token",
        "code",
        "password",
        "secret",
        "client_secret",
        "api_key",
    }
)
REDACTED = "[redacted]"
SCRUBBED_FIELDS = ("arguments", "inputResponses")


class MemoryAudit:
    """Keeps every event in memory, as given, numbered from 1 in `seq`. For tests only."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def record(self, event: dict[str, Any]) -> dict[str, Any]:
        stored = {**copy.deepcopy(event), "seq": len(self.events) + 1}
        self.events.append(stored)
        return stored


def redact(event: dict[str, Any]) -> dict[str, Any]:
    """The event as it may be stored, as a new dict; the caller's event is left alone.

    - "headers" keeps only the header names, sorted; no header value is stored.
    - In "arguments" and "inputResponses", at any depth through dicts and lists, the
      value of every key whose lowercased name is in SECRET_KEYS becomes "[redacted]".
    Every other field is stored as it is, including all protocol and policy evidence:
    request/trace/backend ids, principal/issuer, route, descriptor_pin, decision/reason,
    policy_version/path, latency/result/error, state digests, MRTR round and task id.
    error.code and error.data are protocol evidence, not authorization codes.

    mrtr_round, descriptor_pin, request_meta and result_meta are this exercise's application
    audit fields, not new MCP wire properties. request_meta/result_meta carry the metadata
    already captured from the wire; preserve their keys and values without interpretation.
    Project just this event: do not look up or join any other event.
    """
    stored = copy.deepcopy(event)
    if isinstance(stored.get("headers"), dict):
        stored["headers"] = sorted(stored["headers"])
    for field in SCRUBBED_FIELDS:
        if field in stored:
            stored[field] = _scrub(stored[field])
    return stored


def _scrub(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: REDACTED if isinstance(key, str) and key.lower() in SECRET_KEYS else _scrub(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    return value


class AuditLog(JsonlAuditSink):
    """Project each event before the given sink numbers, appends and flushes it.

    The file API (construction, events and close) is provided by JsonlAuditSink. The candidate
    implements redact: preserving useful single-event evidence while removing the specified
    secrets. No raw event reaches the sink.
    """

    def record(self, event: dict[str, Any]) -> dict[str, Any]:
        """Store one projected event through the provided append-and-flush sink."""
        return self.append(redact(event))
