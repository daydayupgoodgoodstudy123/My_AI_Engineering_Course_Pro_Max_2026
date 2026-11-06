"""Supervision through direct tool calls: the supervisor calls its specialists over JSON-RPC 2.0."""
from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ToolCall:
    """One tool call the supervisor makes: which specialist, and what it should do."""

    specialist: str
    instruction: str


@dataclass(frozen=True)
class ToolResult:
    """A specialist's answer to one call. content is the result, or the error message when ok is False."""

    call_id: int
    specialist: str
    ok: bool
    content: str


class Channel(Protocol):
    """A connection to the specialists. Each frame is one JSON-RPC 2.0 message as JSON text."""

    async def send(self, frame: str) -> None: ...

    async def receive(self) -> str: ...


async def supervise(
    case: Mapping[str, str],
    calls: Sequence[ToolCall],
    views: Mapping[str, Sequence[str]],
    channel: Channel,
) -> AsyncIterator[ToolResult]:
    """Run the supervisor's tool calls against the specialists, all of them at once.

    Call n (counting from 1) is sent as the request
        {"jsonrpc": "2.0", "id": n, "method": specialist,
         "params": {"instruction": instruction, "context": {...}}}.
    The supervisor decides what each specialist sees: context holds exactly the case fields
    listed in views[specialist]; fields the case does not have are left out. A call to a
    specialist with no entry in views raises ValueError before anything is sent.

    Every request is sent before the first reply is awaited. Replies come back in any order
    and are matched to calls by id. A frame without an id is a notification (progress from a
    specialist) and is skipped. A reply with "result" gives ok=True with the result as content;
    one with "error" gives ok=False with error["message"] as content. Each result is yielded as
    soon as its reply arrives, and nothing more is read once every call has its reply.
    """
    raise NotImplementedError
