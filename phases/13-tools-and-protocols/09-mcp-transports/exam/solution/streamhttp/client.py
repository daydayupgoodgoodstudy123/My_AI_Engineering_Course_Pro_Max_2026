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
        content_type = Headers(headers).get("Content-Type") or ""
        media_type = content_type.split(";", 1)[0].strip().lower()
        if media_type not in ("application/json", "text/event-stream"):
            raise ProtocolError(f"unexpected Content-Type {content_type!r}")
        self._request_id = request_id
        self._sse = media_type == "text/event-stream"
        self._buffer = bytearray()
        self._data: list[str] | None = None
        self._notifications: list[dict[str, Any]] = []
        self._response: dict[str, Any] | None = None

    def feed(self, chunk: bytes) -> list[dict[str, Any]]:
        self._buffer += chunk
        if not self._sse:
            return []
        *lines, rest = self._buffer.split(b"\n")
        self._buffer = bytearray(rest)
        messages = []
        for raw in lines:
            line = raw.decode("utf-8")
            if line.endswith("\r"):
                line = line[:-1]
            data = self._line(line)
            if data is not None:
                messages.append(self._accept(_parse(data)))
        return messages

    def finish(self) -> Outcome:
        """The notifications and the final response. A body without one raises StreamLost."""
        if not self._sse:
            self._accept(_parse(self._buffer.decode("utf-8")))
        if self._response is None:
            raise StreamLost("the body ended before the final response")
        return Outcome(list(self._notifications), self._response)

    def _line(self, line: str) -> str | None:
        """Take one SSE line; return an event's data when this line ends the event."""
        if not line:
            data, self._data = self._data, None
            return None if data is None else "\n".join(data)
        if line.startswith(":"):
            return None
        field, _, value = line.partition(":")
        if value.startswith(" "):
            value = value[1:]
        if field == "data":
            if self._data is None:
                self._data = []
            self._data.append(value)
        return None

    def _accept(self, message: Any) -> dict[str, Any]:
        if self._response is not None:
            raise ProtocolError("a message arrived after the final response")
        if not isinstance(message, dict):
            raise ProtocolError("a JSON-RPC message is an object")
        if "method" in message:
            if "id" in message:
                raise ProtocolError("the server sent a request on a request-scoped stream")
            self._notifications.append(message)
            return message
        response_id = message.get("id")
        if type(response_id) is not type(self._request_id) or response_id != self._request_id:
            raise ProtocolError(f"a response to another request: {response_id!r}")
        if "result" not in message and "error" not in message:
            raise ProtocolError("a response carries result or error")
        self._response = message
        return message


def _parse(data: str) -> Any:
    try:
        return json.loads(data)
    except ValueError as exc:
        raise ProtocolError(f"event data is not JSON: {exc}") from exc
