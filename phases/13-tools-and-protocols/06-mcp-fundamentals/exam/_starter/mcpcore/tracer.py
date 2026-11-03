"""A stateless request tracer: one line per message, written as the messages arrive."""
from __future__ import annotations

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
    raise NotImplementedError
