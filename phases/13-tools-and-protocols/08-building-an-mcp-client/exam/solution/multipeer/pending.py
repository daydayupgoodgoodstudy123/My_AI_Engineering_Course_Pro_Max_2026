"""Requests in flight on one transport, matched to their answers by JSON-RPC id."""
from __future__ import annotations

from typing import Any

from .protocol import ProtocolError, valid_id


class PendingCalls:
    """The requests a transport has sent and not yet seen answered.

    Answers may come back in any order. An answer belongs to the pending request whose id has the
    same type and value; any other answer is rejected and leaves every pending request in place.
    """

    def __init__(self) -> None:
        # keyed by (type, id): True == 1 and hash(True) == hash(1), so the bare id is not enough
        self._waiting: dict[tuple[type, Any], tuple[dict, Any]] = {}

    def __len__(self) -> int:
        return len(self._waiting)

    def add(self, request: dict, waiter: Any = None) -> None:
        """Track a request until its answer arrives. waiter is handed back with the request."""
        request_id = request.get("id")
        if not valid_id(request_id):
            raise ValueError(f"a request id is a string or an integer, got {request_id!r}")
        key = (type(request_id), request_id)
        if key in self._waiting:
            raise ValueError(f"request {request_id!r} is already in flight")
        self._waiting[key] = (request, waiter)

    def resolve(self, response: dict) -> tuple[dict, Any]:
        """Remove and return (request, waiter) for the request this response answers."""
        response_id = response.get("id") if isinstance(response, dict) else None
        entry = None
        if valid_id(response_id):
            entry = self._waiting.pop((type(response_id), response_id), None)
        if entry is None:
            raise ProtocolError(f"no pending request has id {response_id!r}")
        return entry

    def drain(self) -> list[tuple[dict, Any]]:
        """Remove and return everything still in flight, oldest first: the transport is gone."""
        entries = list(self._waiting.values())
        self._waiting.clear()
        return entries
