"""Request-scoped SSE from one backend to one client, and where every task lives."""
from __future__ import annotations

import json
from collections.abc import AsyncGenerator, AsyncIterator
from dataclasses import dataclass
from typing import Any

from .wire import gateway_result


@dataclass(frozen=True)
class Hop:
    """One relayed request.

    The client's request id and progress token (None when it asked for no progress),
    the id of the gateway's request to the backend (also the progress token the gateway
    gave that backend), whose call it is as (issuer, principal), and the backend's name.
    """

    client_id: int | str
    backend_id: str
    progress_token: int | str | None
    owner: tuple[str, str]
    backend: str


class TaskNotFound(Exception):
    """No task with this id belongs to this caller."""


class TaskRoutes:
    """taskId -> (owner, backend): application state keyed by the task handle, not a session."""

    def __init__(self) -> None:
        self._routes: dict[str, tuple[tuple[str, str], str]] = {}

    def record(self, task_id: str, owner: tuple[str, str], backend: str) -> None:
        """Remember which backend holds a task and whose task it is."""
        self._routes[task_id] = (owner, backend)

    def resolve(self, task_id: str, owner: tuple[str, str]) -> str:
        """The backend that holds `task_id` for `owner`.

        Raises TaskNotFound when there is no such task or it belongs to someone else;
        the two look the same to the caller.
        """
        route = self._routes.get(task_id)
        if route is None or route[0] != owner:
            raise TaskNotFound(task_id)
        return route[1]


async def relay(
    messages: AsyncGenerator[dict[str, Any], None], hop: Hop, tasks: TaskRoutes
) -> AsyncIterator[bytes]:
    """Relay one backend's request-scoped stream to the client as SSE.

    `messages` yields the JSON-RPC messages the backend writes for request
    `hop.backend_id`. The client gets each of these as one SSE event, a single
    `data: <JSON>` line and a blank line, in UTF-8:

    - every notifications/progress for the gateway's token (`hop.backend_id`), as soon
      as it arrives, under the client's own token `hop.progress_token`, and nothing at
      all when the client asked for no progress;
    - then the backend's response to `hop.backend_id`, under the client's id
      `hop.client_id`, its result with the gateway's serverInfo in place of the
      backend's _meta (see gateway_result) and everything else in it, requestState
      included, untouched;
    - and nothing after that response: the stream ends there.

    Anything else the backend writes is dropped. When the response is a task, the task
    is recorded in `tasks` for `hop.owner` and `hop.backend` before the client sees its
    taskId. When the client goes away early, `messages` is closed, which cancels the
    backend request; a task already recorded stays routable.
    """
    try:
        async for message in messages:
            if message.get("id") == hop.backend_id and ("result" in message or "error" in message):
                if "error" in message:
                    reply = {"jsonrpc": "2.0", "id": hop.client_id, "error": message["error"]}
                else:
                    result = message["result"]
                    if result.get("resultType") == "task":
                        tasks.record(result["taskId"], hop.owner, hop.backend)
                    reply = {"jsonrpc": "2.0", "id": hop.client_id, "result": gateway_result(result)}
                yield _event(reply)
                return
            params = message.get("params")
            if (
                message.get("method") == "notifications/progress"
                and "id" not in message
                and isinstance(params, dict)
                and params.get("progressToken") == hop.backend_id
                and hop.progress_token is not None
            ):
                yield _event({**message, "params": {**params, "progressToken": hop.progress_token}})
    finally:
        await messages.aclose()


def _event(message: dict[str, Any]) -> bytes:
    return b"data: " + json.dumps(message, ensure_ascii=False).encode("utf-8") + b"\n\n"
