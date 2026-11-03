"""subscriptions/listen: push task snapshots over the SSE stream of the POST response."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from .task import TERMINAL_STATUSES
from .wire import (
    SUBSCRIPTION_ID_META,
    McpError,
    require_tasks_extension,
    server_meta,
    validate_request_meta,
)


async def listen(
    service,
    request: dict[str, Any],
    *,
    principal: str,
    ticks: AsyncIterator[object],
) -> AsyncIterator[str]:
    """Serve one subscriptions/listen request from principal as an SSE stream.

    params.notifications.taskIds lists the tasks to watch. Like every task method, the
    request must declare the Tasks extension; an invalid request raises McpError before
    anything is sent.

    Each message is one SSE event, yielded as one string: a "data: " line holding the
    message's JSON text, then a blank line. The first message is
    notifications/subscriptions/acknowledged; its params.notifications.taskIds are the
    requested ids that name a task the caller owns, in request order, each once. Any
    other id is dropped without a word. Every message carries
    io.modelcontextprotocol/subscriptionId in its _meta, equal to the request id.

    After that, each item from ticks means "look again". On every tick, each watched
    task whose snapshot differs from the last one sent (or from the one it had at the
    acknowledgement) is sent as notifications/tasks, with the snapshot as params: what
    tasks/get returns at that moment, without resultType and with the subscription id
    as _meta. A task stops being watched once a finished snapshot has been sent. When no
    task is left to watch (or ticks run out), the stream ends with the listen request's
    result: complete, with the subscription id next to serverInfo in its _meta.
    """
    params = request.get("params")
    if not isinstance(params, dict):
        raise McpError(-32602, "params must be an object")
    meta = validate_request_meta(params)
    require_tasks_extension(meta)
    notifications = params.get("notifications")
    requested = notifications.get("taskIds") if isinstance(notifications, dict) else None
    if not isinstance(requested, list):
        raise McpError(-32602, "notifications.taskIds must be a list")
    tag = {SUBSCRIPTION_ID_META: request.get("id")}

    def snapshot(task_id: Any) -> dict[str, Any]:
        result = service.tasks_get({"taskId": task_id, "_meta": meta}, principal=principal)
        return {key: value for key, value in result.items() if key not in ("resultType", "_meta")}

    accepted: list[str] = []
    last: dict[str, dict[str, Any]] = {}
    for task_id in requested:
        if task_id in accepted:
            continue
        try:
            current = snapshot(task_id)
        except McpError:
            continue
        accepted.append(task_id)
        last[task_id] = current
    watching = [task_id for task_id in accepted if last[task_id]["status"] not in TERMINAL_STATUSES]
    yield _event(
        {
            "jsonrpc": "2.0",
            "method": "notifications/subscriptions/acknowledged",
            "params": {"notifications": {"taskIds": list(accepted)}, "_meta": dict(tag)},
        }
    )
    if watching:
        async for _ in ticks:
            for task_id in list(watching):
                try:
                    current = snapshot(task_id)
                except McpError:
                    watching.remove(task_id)
                    continue
                if current != last[task_id]:
                    last[task_id] = current
                    yield _event(
                        {
                            "jsonrpc": "2.0",
                            "method": "notifications/tasks",
                            "params": {**current, "_meta": dict(tag)},
                        }
                    )
                if current["status"] in TERMINAL_STATUSES:
                    watching.remove(task_id)
            if not watching:
                break
    yield _event(
        {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": {"resultType": "complete", "_meta": {**server_meta(), **tag}},
        }
    )


def _event(message: dict[str, Any]) -> str:
    return f"data: {json.dumps(message, separators=(',', ':'))}\n\n"
