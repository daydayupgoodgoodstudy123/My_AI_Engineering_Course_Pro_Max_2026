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
    raise NotImplementedError
