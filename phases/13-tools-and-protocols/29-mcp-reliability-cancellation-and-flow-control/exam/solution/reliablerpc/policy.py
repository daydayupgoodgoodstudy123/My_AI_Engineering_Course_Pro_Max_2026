"""What a client may retry, and the signal that abandons a request on each transport."""
from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Union

from .wire import STDIO, STREAMABLE_HTTP, ReliabilityError, notification


@dataclass(frozen=True)
class ToolContract:
    """What the application itself guarantees about a tool, independent of the server's annotations.

    side_effect: calling the tool changes something.
    idempotency_key: the argument the server deduplicates on, durably; None when it deduplicates nothing.
    """

    side_effect: bool
    idempotency_key: str | None = None


@dataclass(frozen=True)
class Call:
    """A request the client sent and is still tracking."""

    request_id: int | str
    method: str
    params: dict[str, Any]
    transport: str
    task_id: str | None = None  # set once tools/call answered with a durable task


@dataclass(frozen=True)
class Notify:
    """Send this notification exactly as it is. Nothing answers it."""

    message: dict[str, Any]


@dataclass(frozen=True)
class NewRequest:
    """Send an ordinary request; the transport gives it a fresh JSON-RPC id."""

    method: str
    params: dict[str, Any]


@dataclass(frozen=True)
class CloseStream:
    """Close the response stream of request_id. Nothing is sent."""

    request_id: int | str


CancelSignal = Union[Notify, NewRequest, CloseStream]


@dataclass(frozen=True)
class RetryDecision:
    """classification is "safe", "conditional" or "unsafe".

    resend is the tools/call to send again, or None: do not retry automatically, reconcile first.
    """

    classification: str
    resend: NewRequest | None


def classify_retry(
    call: Call,
    contracts: Mapping[str, ToolContract],
    tools: Mapping[str, dict[str, Any]] | None = None,
) -> RetryDecision:
    """Decide whether a tools/call that failed or timed out may be sent again.

    contracts is the application's own contract for each tool, by name. tools is what the
    server's tools/list says about them; annotations such as readOnlyHint and idempotentHint are
    untrusted hints and never change the decision.

    - safe: no side effect. Send the same params again.
    - conditional: a side effect that the server deduplicates on contract.idempotency_key, and
      the call carries a non-empty string under that argument. Send the same params again: same
      key, identical arguments.
    - unsafe: any other side effect, and any tool without a contract. Do not resend.
    """
    if call.method != "tools/call":
        raise ReliabilityError(f"only tools/call is classified, not {call.method}")
    contract = contracts.get(call.params.get("name"))
    if contract is None:
        return RetryDecision("unsafe", None)
    if not contract.side_effect:
        return RetryDecision("safe", NewRequest("tools/call", copy.deepcopy(call.params)))
    arguments = call.params.get("arguments") or {}
    key = arguments.get(contract.idempotency_key) if contract.idempotency_key else None
    if isinstance(key, str) and key:
        return RetryDecision("conditional", NewRequest("tools/call", copy.deepcopy(call.params)))
    return RetryDecision("unsafe", None)


def cancel_signal(call: Call, *, reason: str | None = None) -> CancelSignal:
    """What the client puts on the wire to abandon call.

    - A call that became a durable task (task_id set) is cancelled with tasks/cancel, an
      ordinary request whose params carry taskId. Its tools/call already finished, so closing a
      stream or naming the request cannot reach the task.
    - stdio: notifications/cancelled, whose params carry requestId (the call's id exactly as it
      was sent) and reason when one is given.
    - Streamable HTTP: close the call's response stream. Nothing is posted.
    """
    if call.task_id is not None:
        return NewRequest("tasks/cancel", {"taskId": call.task_id})
    if call.transport == STDIO:
        return Notify(_cancelled(call, reason))
    if call.transport == STREAMABLE_HTTP:
        return CloseStream(call.request_id)
    raise ReliabilityError(f"unsupported transport {call.transport!r}")


def server_cancel_signal(call: Call, *, reason: str | None = None) -> Notify:
    """What the server sends to end a request it is serving.

    A server never cancels a client's calls. The one request it may end with
    notifications/cancelled is a subscriptions/listen on stdio; anything else raises
    ReliabilityError.
    """
    if call.transport != STDIO or call.method != "subscriptions/listen":
        raise ReliabilityError("server-sent notifications/cancelled is reserved for stdio subscriptions/listen")
    return Notify(_cancelled(call, reason))


def _cancelled(call: Call, reason: str | None) -> dict[str, Any]:
    params: dict[str, Any] = {"requestId": call.request_id}
    if reason is not None:
        params["reason"] = reason
    return notification("notifications/cancelled", params)
