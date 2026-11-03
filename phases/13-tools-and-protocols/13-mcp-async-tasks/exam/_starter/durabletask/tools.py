"""Task-backed tools, and what one step of a tool's work can return."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Union

from .task import DEFAULT_POLL_INTERVAL_MS, DEFAULT_TTL_MS


@dataclass(frozen=True)
class NeedInput:
    """The tool cannot go on until the client answers these input requests, by key."""

    requests: dict[str, Any]
    message: str = "Waiting for input."


@dataclass(frozen=True)
class Done:
    """The tool finished. result is its CallToolResult: content, structuredContent, isError."""

    result: dict[str, Any]
    message: str = "Completed."


Outcome = Union[NeedInput, Done]


@dataclass(frozen=True)
class Tool:
    """A tool whose calls become tasks.

    run(arguments, answers) does the next piece of work and returns an Outcome, or raises
    McpError when the call fails with a JSON-RPC error. answers holds the client's
    responses so far, by input key. ttl_ms is the ttl of the tasks it creates (None: no
    limit) and poll_interval_ms their pollIntervalMs.
    """

    run: Callable[[dict[str, Any], dict[str, Any]], Outcome]
    ttl_ms: int | None = DEFAULT_TTL_MS
    poll_interval_ms: int = DEFAULT_POLL_INTERVAL_MS
