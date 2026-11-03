"""The task record: what a task holds, how tasks/get shows it, and when it expires."""
from __future__ import annotations

import copy
import random
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from .wire import format_time

STATUSES = ("working", "input_required", "completed", "cancelled", "failed")
TERMINAL_STATUSES = frozenset({"completed", "cancelled", "failed"})
DEFAULT_TTL_MS = 900_000
DEFAULT_POLL_INTERVAL_MS = 1_000
EXPIRED_MESSAGE = "Task expired."
EXPIRED_ERROR = {"code": -32603, "message": "Task expired"}
TASK_ID = re.compile(r"tsk_[0-9a-f]{12}")


def new_task_id(rng: random.Random) -> str:
    """A fresh task id: tsk_ and 12 lowercase hex digits."""
    return f"tsk_{rng.getrandbits(48):012x}"


def check_task_id(value: Any) -> str:
    """Return value if it is a task id this service could have minted; ValueError otherwise."""
    if not isinstance(value, str) or TASK_ID.fullmatch(value) is None:
        raise ValueError(f"malformed task id: {value!r}")
    return value


@dataclass
class Task:
    """One durable task.

    created_at and last_updated_at are aware UTC datetimes in whole seconds. ttl_ms is
    None when the task has no limit. input_requests holds the requests still waiting for
    an answer, by input key; issued_keys every key ever issued, in order; answers the
    accepted responses, by key. result is set once the task completes, error once it
    fails. cancel_requested records a tasks/cancel the worker has not acted on yet.
    """

    task_id: str
    owner: str
    tool: str
    arguments: dict[str, Any]
    status: str
    status_message: str
    created_at: datetime
    last_updated_at: datetime
    ttl_ms: int | None
    poll_interval_ms: int = DEFAULT_POLL_INTERVAL_MS
    input_requests: dict[str, Any] = field(default_factory=dict)
    answers: dict[str, Any] = field(default_factory=dict)
    issued_keys: list[str] = field(default_factory=list)
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    cancel_requested: bool = False

    def to_wire(self) -> dict[str, Any]:
        """The task as tasks/get shows it, without the resultType and _meta around it.

        Status-specific fields appear only with their status: inputRequests while
        input_required, result once completed, error once failed.
        """
        wire: dict[str, Any] = {
            "taskId": self.task_id,
            "status": self.status,
            "statusMessage": self.status_message,
            "createdAt": format_time(self.created_at),
            "lastUpdatedAt": format_time(self.last_updated_at),
            "ttlMs": self.ttl_ms,
            "pollIntervalMs": self.poll_interval_ms,
        }
        if self.status == "input_required":
            wire["inputRequests"] = copy.deepcopy(self.input_requests)
        elif self.status == "completed":
            wire["result"] = copy.deepcopy(self.result)
        elif self.status == "failed":
            wire["error"] = copy.deepcopy(self.error)
        return wire

    def expires_at(self) -> datetime | None:
        """When the task's ttl runs out: ttl_ms after created_at. None when it has no limit."""
        if self.ttl_ms is None:
            return None
        return self.created_at + timedelta(milliseconds=self.ttl_ms)
