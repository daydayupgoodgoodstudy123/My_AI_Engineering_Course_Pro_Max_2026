"""Where the gateway's audit events go: memory for tests, an append-only JSONL file for real."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

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
    Every other field is stored as it is.
    """
    raise NotImplementedError


class AuditLog:
    """An append-only JSONL audit log: one JSON object per line, in the order recorded.

    Opening a log keeps every line already in the file, including lines other gateway
    replicas wrote. Each recorded event is redacted first (see redact), so no secret
    ever reaches the disk, and gets the next `seq`: the number of events in the file,
    counting the ones already there when it was opened. An event is on disk, readable
    by any other reader, by the time record returns.
    """

    def __init__(self, path: str | Path) -> None:
        raise NotImplementedError

    def record(self, event: dict[str, Any]) -> dict[str, Any]:
        """Redact, number and append one event; return it as stored."""
        raise NotImplementedError

    def events(self) -> list[dict[str, Any]]:
        """Every event in the file, in the order written, exactly as stored."""
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError
