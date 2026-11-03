"""The client side: decode one Streamable HTTP response, layer by layer."""
from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .wire import Headers


class ProtocolError(Exception):
    """The response breaks the transport contract."""


class StreamLost(ProtocolError):
    """The body ended before the final response, so the request is lost.

    Retry it, if that is safe, as a new request with a new id. A modern stream is never resumed.
    """


@dataclass
class Outcome:
    notifications: list[dict[str, Any]]
    response: dict[str, Any]


class ResponseReader:
    """Decode the body of a 200 response to the request whose id is request_id.

    HTTP: Content-Type picks the format. Its media type is compared case-insensitively and its
    parameters, such as charset, are ignored. application/json is a body holding one JSON-RPC
    response; text/event-stream is a request-scoped SSE stream. Anything else is a ProtocolError.

    SSE, in UTF-8: lines end with LF or CRLF. A line starting with ":" is a comment. Any other
    line is "field: value"; one space after the colon is dropped, and a line without a colon is
    a field with an empty value. The data lines of an event are joined with "\\n", and a blank
    line ends the event. An event without data is ignored, and so is every field but data. An
    event that the body ends in the middle of is dropped.

    JSON-RPC: each event's data is one message. Notifications belong to the request and are kept
    in order. The response whose id equals request_id, in value and in type, is the final
    response, and no message may follow it. A request from the server, or a response to another
    id, is a ProtocolError.

    feed() takes body bytes exactly as they arrive, in chunks of any size, and returns the
    messages that those bytes complete. finish() is called once, when the body has ended.
    """

    def __init__(self, request_id: int | str, headers: Iterable[tuple[str, str]]) -> None:
        raise NotImplementedError

    def feed(self, chunk: bytes) -> list[dict[str, Any]]:
        raise NotImplementedError

    def finish(self) -> Outcome:
        """The notifications and the final response. A body without one raises StreamLost."""
        raise NotImplementedError
