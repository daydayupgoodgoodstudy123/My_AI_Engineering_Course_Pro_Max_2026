"""Where the gateway's audit events go: memory for tests, an append-only JSONL file for real."""
from __future__ import annotations

import copy
import json
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


class AuditLog:
    """An append-only JSONL audit log: one JSON object per line, in the order recorded.

    Opening a log keeps every line already in the file, including lines other gateway
    replicas wrote. Each recorded event is redacted first (see redact), so no secret
    ever reaches the disk, and gets the next `seq`: the number of events in the file,
    counting the ones already there when it was opened. An event is on disk, readable
    by any other reader, by the time record returns.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.touch()
        self._count = len(self.events())
        self._file = self.path.open("a", encoding="utf-8")

    def record(self, event: dict[str, Any]) -> dict[str, Any]:
        """Redact, number and append one event; return it as stored."""
        stored = {**redact(event), "seq": self._count + 1}
        self._file.write(json.dumps(stored) + "\n")
        self._file.flush()
        self._count += 1
        return stored

    def events(self) -> list[dict[str, Any]]:
        """Every event in the file, in the order written, exactly as stored."""
        return [json.loads(line) for line in self._lines()]

    def close(self) -> None:
        self._file.close()

    def _lines(self) -> list[str]:
        text = self.path.read_text(encoding="utf-8")
        return [line for line in text.split("\n") if line]
