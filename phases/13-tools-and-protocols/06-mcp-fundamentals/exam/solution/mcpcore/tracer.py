"""A stateless request tracer: one line per message, written as the messages arrive."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from .wire import CAPABILITIES_KEY, VERSION_KEY

MODERN_ERRORS = frozenset({-32020, -32021, -32022})


async def trace(messages: AsyncIterator[Any]) -> AsyncIterator[str]:
    """Label each message on its own and yield one line for it as soon as it arrives:

        [kind/era] method: detail

    Requests have an "id" and a string "method":
      initialize -> request/legacy, detail "connection-scoped handshake";
      params._meta holding both the protocol version and the client capabilities ->
      request/modern, detail "version=<version> capabilities=current-request";
      anything else -> request/invalid, detail "missing modern request metadata".
    Notifications have a string "method" and no "id": notification/legacy for
    notifications/initialized, notification/unknown for the rest; detail "no response expected".
    Responses have an "id" and a "result" or an "error". A response answers the pending request
    with the same id, and method is that request's method. Once answered, a request is no
    longer pending, so a second response to it, or a response nobody asked for, is kind
    "orphan" with method "?".
      error: era modern for codes -32020, -32021 and -32022, unknown for any other code;
      detail "code=<code>".
      result: era modern when it has a resultType, legacy without one only when it answers
      initialize, invalid otherwise; detail "resultType=<resultType, or absent>".
    Anything else is "[unknown/invalid] : not a JSON-RPC message".
    """
    pending: dict[str, str] = {}
    async for message in messages:
        kind, era, method, detail = _label(message, pending)
        yield f"[{kind}/{era}] {method}: {detail}\n"


def _key(request_id: Any) -> str:
    return json.dumps(request_id, sort_keys=True)


def _label(message: Any, pending: dict[str, str]) -> tuple[str, str, str, str]:
    if not isinstance(message, dict):
        return "unknown", "invalid", "", "not a JSON-RPC message"
    method = message.get("method")
    if isinstance(method, str) and "id" in message:
        if method == "initialize":
            era, detail = "legacy", "connection-scoped handshake"
        else:
            params = message.get("params")
            meta = params.get("_meta") if isinstance(params, dict) else None
            if isinstance(meta, dict) and VERSION_KEY in meta and CAPABILITIES_KEY in meta:
                era, detail = "modern", f"version={meta[VERSION_KEY]} capabilities=current-request"
            else:
                era, detail = "invalid", "missing modern request metadata"
        pending[_key(message["id"])] = method
        return "request", era, method, detail
    if isinstance(method, str):
        era = "legacy" if method == "notifications/initialized" else "unknown"
        return "notification", era, method, "no response expected"
    if "id" in message and ("result" in message or "error" in message):
        answered = pending.pop(_key(message["id"]), None)
        kind, request_method = ("response", answered) if answered is not None else ("orphan", "?")
        if "error" in message:
            error = message["error"]
            code = error.get("code", "absent") if isinstance(error, dict) else "absent"
            era = "modern" if isinstance(code, int) and code in MODERN_ERRORS else "unknown"
            return kind, era, request_method, f"code={code}"
        result = message["result"]
        result_type = result.get("resultType") if isinstance(result, dict) else None
        if result_type is not None:
            era = "modern"
        elif request_method == "initialize":
            era = "legacy"
        else:
            era = "invalid"
        return kind, era, request_method, f"resultType={'absent' if result_type is None else result_type}"
    return "unknown", "invalid", "", "not a JSON-RPC message"
