"""The client side of URL-mode elicitation: show, ask, open, then retry until the server is done."""
from __future__ import annotations

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
    raise NotImplementedError
