"""Requests in flight on one transport, matched to their answers by JSON-RPC id."""
from __future__ import annotations

from typing import Any

from .protocol import ProtocolError, same_id, valid_id


class PendingCalls:
    """The requests a transport has sent and not yet seen answered.

    Answers may come back in any order. An answer belongs to the pending request whose id has the
    same type and value; any other answer is rejected and leaves every pending request in place.
    """

    def __init__(self) -> None:
        self._waiting: list[tuple[dict, Any]] = []

    def __len__(self) -> int:
        return len(self._waiting)

    def add(self, request: dict, waiter: Any = None) -> None:
        """Track a request until its answer arrives. waiter is handed back with the request."""
        request_id = request.get("id")
        if not valid_id(request_id):
            raise ValueError(f"a request id is a string or an integer, got {request_id!r}")
        if any(same_id(pending["id"], request_id) for pending, _ in self._waiting):
            raise ValueError(f"request {request_id!r} is already in flight")
        self._waiting.append((request, waiter))

    def resolve(self, response: dict) -> tuple[dict, Any]:
        """Remove and return (request, waiter) for the request this response answers."""
        response_id = response.get("id") if isinstance(response, dict) else None
        for index, (request, waiter) in enumerate(self._waiting):
            if same_id(request["id"], response_id):
                del self._waiting[index]
                return request, waiter
        raise ProtocolError(f"no pending request has id {response_id!r}")

    def drain(self) -> list[tuple[dict, Any]]:
        """Remove and return everything still in flight, oldest first: the transport is gone."""
        entries, self._waiting = self._waiting, []
        return entries
