"""The main model's tool calls arrive as JSON-RPC 2.0 requests, one per line."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from typing import Any

from .content import Content
from .gate import REFUSAL, ToolCall, Verdict

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
REFUSED = -32001  # a server error code, from the range JSON-RPC 2.0 leaves to implementations


def _line(request_id: Any, **body: Any) -> str:
    return json.dumps({"jsonrpc": "2.0", "id": request_id, **body}) + "\n"


def _error(request_id: Any, code: int, message: str) -> str:
    return _line(request_id, error={"code": code, "message": message})


def handle_line(
    line: str,
    validate: Callable[[ToolCall, list[Content]], Verdict],
    tools: dict[str, Callable[..., str]],
    history: list[Content],
    intent: str,
    confirm: Callable[[ToolCall], bool],
) -> str | None:
    """Handle one line under serve's JSON-RPC contract; return reply text or None.

    Blank lines and notifications return None. Notifications still validate and
    may execute. Check each call against the caller's current history, and append
    only real tool output with its untrusted source before returning. A refusal
    changes neither the world nor the evidence history. Only a confirm verdict
    asks the human; an approval allows this call. Reply ids retain their types.
    """
    raise NotImplementedError


async def serve(
    lines: AsyncIterator[str],
    validate: Callable[[ToolCall, list[Content]], Verdict],
    tools: dict[str, Callable[..., str]],
    history: list[Content],
    intent: str,
    confirm: Callable[[ToolCall], bool],
) -> AsyncIterator[str]:
    """Provided transport loop: handle one line, yield its reply, then read the next.

    Validate and run each tool call as it arrives; yield one reply line per answered request.

    Each line holds one request object: {"jsonrpc": "2.0", "id": ..., "method": <tool name>,
    "params": <the tool's arguments as an object; may be left out>}. Blank lines are skipped.
    A request without an "id" member is a notification: it is handled like any other call but
    never answered, not even with an error. Replies echo the request's id as it was sent.

    Each call becomes ToolCall(method, params, intent) and is checked with
    validate(call, history) against the history as of that call. "confirm" asks confirm(call).
    An allowed call runs at once; its result string is the reply's "result" and is appended to
    history as tool_output before the next line is read; nothing else joins the history. A
    refused or declined call never runs and gets the error {"code": REFUSED, "message": REFUSAL}.

    Errors, with the standard JSON-RPC messages: a line that is not JSON gets PARSE_ERROR
    "Parse error", and a line that is not a request object (not a JSON object, or without a
    string "method") gets INVALID_REQUEST "Invalid Request", both with id null. A method that is
    not a tool gets METHOD_NOT_FOUND "Method not found", and params that are not an object get
    INVALID_PARAMS "Invalid params". These are answered without calling validate. Each reply is
    one line of JSON ending in "\\n", yielded as soon as its request is handled.
    """
    async for line in lines:
        reply = handle_line(line, validate, tools, history, intent, confirm)
        if reply is not None:
            yield reply
