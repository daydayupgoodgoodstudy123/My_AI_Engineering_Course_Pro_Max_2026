"""The server side of in-flight requests: progress, completion, and cancellation races."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .buffer import BoundedSseBuffer
from .wire import (
    CANCELLED,
    COMPLETED,
    IN_PROGRESS,
    STDIO,
    STREAMABLE_HTTP,
    ReliabilityError,
    progress_notification,
    response,
)


@dataclass
class InFlightRequest:
    request_id: int | str
    operation: str
    transport: str
    progress_token: int | str | None = None
    stream: BoundedSseBuffer | None = None  # the request's own response stream on Streamable HTTP
    state: str = IN_PROGRESS
    last_progress: int | float | None = None
    cancel_reason: str | None = None
    response: dict[str, Any] | None = None


class RequestCoordinator:
    """Tracks every request the server is working on and writes what each one sends.

    stdio requests share one channel. Each Streamable HTTP request writes to its own response
    stream, which closes when the client cancels.

    A request ends in exactly one terminal state, and whichever of completion and cancellation
    the server observes first wins:
    - once cancelled, a request sends nothing more: no progress, no response;
    - once completed, a request keeps its response, and a late cancellation changes nothing.
    """

    def __init__(self, channel: BoundedSseBuffer, *, stream_capacity: int = 8) -> None:
        self.channel = channel
        self.stream_capacity = stream_capacity
        self.requests: dict[int | str, InFlightRequest] = {}

    def start(
        self,
        request_id: int | str,
        operation: str,
        *,
        transport: str,
        progress_token: int | str | None = None,
    ) -> InFlightRequest:
        if type(request_id) not in (int, str):
            raise ReliabilityError("request id must be an integer or string")
        if progress_token is not None and type(progress_token) not in (int, str):
            raise ReliabilityError("progress token must be an integer or string")
        if request_id in self.requests:
            raise ReliabilityError("request ids must be unique while tracked")
        if transport not in (STDIO, STREAMABLE_HTTP):
            raise ReliabilityError(f"unsupported transport {transport!r}")
        stream = BoundedSseBuffer(self.stream_capacity) if transport == STREAMABLE_HTTP else None
        request = InFlightRequest(request_id, operation, transport, progress_token, stream)
        self.requests[request_id] = request
        return request

    def progress(
        self,
        request_id: int | str,
        value: int | float,
        *,
        total: int | float | None = None,
        message: str | None = None,
    ) -> dict[str, Any] | None:
        """Send progress for a request that is still running and has a progress token.

        Returns the notification, or None when the request has ended or has no progress token.
        The first value may be zero. Every later value must be strictly greater than the last
        one sent; a repeated or smaller value raises ReliabilityError without sending anything
        or changing last_progress. Ended requests are ignored before values are checked.
        """
        request = self.requests[request_id]
        if request.progress_token is None:
            return None
        if request.last_progress is not None and value < request.last_progress:
            raise ReliabilityError("progress must increase")
        note = progress_notification(request.progress_token, value, total, message)
        self._outbox(request).push_progress(note)
        request.last_progress = value
        return note

    def complete(self, request_id: int | str, result: dict[str, Any]) -> dict[str, Any] | None:
        """Finish a request and send its response.

        Returns the response, or None when cancellation already won. Completing a completed
        request again returns the response it already sent, and sends nothing.
        """
        request = self.requests[request_id]
        if request.state == COMPLETED:
            return request.response
        message = response(request_id, result)
        self._outbox(request).push_final(message)
        request.state = COMPLETED
        request.response = message
        return message

    def receive_stdio_cancellation(self, notification: Any) -> None:
        """Handle notifications/cancelled from a stdio client. It is a notification: never answered.

        Malformed notifications, unknown request ids and requests on another transport are ignored.
        """
        if not isinstance(notification, dict) or notification.get("method") != "notifications/cancelled":
            return None
        params = notification.get("params")
        if not isinstance(params, dict):
            return None
        request_id = params.get("requestId")
        if type(request_id) not in (int, str):
            return None
        request = self.requests.get(request_id)
        if request is None or request.transport != STDIO:
            return None
        reason = params.get("reason")
        self._cancel(request, reason if isinstance(reason, str) else None)
        return None

    def close_http_stream(self, request_id: int | str, *, reason: str = "response stream closed") -> None:
        """The client closed a Streamable HTTP request's response stream: that is its cancellation."""
        request = self.requests.get(request_id)
        if request is None or request.transport != STREAMABLE_HTTP:
            return None
        self._cancel(request, reason)
        request.stream.close()
        return None

    def _cancel(self, request: InFlightRequest, reason: str | None) -> None:
        """Cancel a request, unless it has already finished."""
        if request.state != IN_PROGRESS:
            return
        request.state = CANCELLED
        request.cancel_reason = reason

    def _outbox(self, request: InFlightRequest) -> BoundedSseBuffer:
        return request.stream if request.stream is not None else self.channel
