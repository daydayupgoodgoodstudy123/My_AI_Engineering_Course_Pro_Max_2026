"""The client side of URL-mode elicitation: show, ask, open, then retry until the server is done."""
from __future__ import annotations

import copy
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from .protocol import McpError


async def drive_url_elicitation(
    send: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
    request: dict[str, Any],
    *,
    consent: Callable[[str, str], str],
    open_url: Callable[[str], None],
    ticks: AsyncIterator[Any],
) -> AsyncIterator[str]:
    """Carry one tools/call request (with an integer id) through URL-mode elicitation.

    send delivers a request and returns the JSON-RPC response; an error response raises
    McpError. When the server answers input_required with a URL-mode elicitation/create,
    show the user the full URL and the message by calling consent(url, message), which
    returns "accept", "decline" or "cancel". Open the URL with open_url only after an
    accept, never before and never twice.

    An accept only means the user agreed to open the URL. Wait for the next item from
    ticks, then retry the original request with a fresh id (the original id plus one,
    plus two, ...), the latest requestState and inputResponses {key: {"action": "accept"}}.
    Until the out-of-band flow completes, the server answers input_required for the same
    URL again: keep waiting for ticks and retrying, without asking or opening again. On a
    decline or a cancel, retry once straight away with that action, then stop. When ticks
    runs out, stop.

    Yield one JSON object per line, newline-terminated, as each action happens:
        {"event": "show_url", "id": <id of the answered request>, "url": ..., "message": ...}
        {"event": "open", "url": ...}
        {"event": "retry", "id": <new id>, "action": "accept" | "decline" | "cancel"}
        {"event": "complete", "id": <id of the request the server completed>}
        {"event": "refused", "id": <id>, "action": "decline" | "cancel"}
    """

    def line(**event: Any) -> str:
        return json.dumps(event) + "\n"

    request_id = request["id"]
    response = await send(request)
    opened: set[str] = set()
    while True:
        if "error" in response:
            error = response["error"]
            raise McpError(error["code"], error["message"], error.get("data"))
        result = response["result"]
        if result.get("resultType") != "input_required":
            yield line(event="complete", id=response["id"])
            return
        ((key, ask),) = result["inputRequests"].items()
        params = ask["params"]
        if ask.get("method") != "elicitation/create" or params.get("mode") != "url":
            raise ValueError(f"expected one URL-mode elicitation, got {ask!r}")
        url = params["url"]
        if url in opened:
            action = "accept"
        else:
            yield line(event="show_url", id=response["id"], url=url, message=params["message"])
            action = consent(url, params["message"])
            if action not in ("accept", "decline", "cancel"):
                raise ValueError(f"consent must return accept, decline or cancel, got {action!r}")
            if action == "accept":
                open_url(url)
                opened.add(url)
                yield line(event="open", url=url)
        if action == "accept":
            try:
                await ticks.__anext__()
            except StopAsyncIteration:
                return
        request_id += 1
        retry = copy.deepcopy(request)
        retry["id"] = request_id
        retry["params"]["inputResponses"] = {key: {"action": action}}
        retry["params"]["requestState"] = result["requestState"]
        response = await send(retry)
        yield line(event="retry", id=request_id, action=action)
        if action != "accept":
            if "error" in response:
                error = response["error"]
                raise McpError(error["code"], error["message"], error.get("data"))
            yield line(event="refused", id=request_id, action=action)
            return
