"""In-process backend MCP servers behind the gateway. The tests script their tools."""
from __future__ import annotations

import copy
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

from .wire import SERVER_INFO_META, ProtocolError, error_response, success, validate_wire

Tool = Callable[[dict[str, Any]], dict[str, Any]]
StreamTool = Callable[[str, dict[str, Any]], AsyncIterator[dict[str, Any]]]


@dataclass(frozen=True)
class Received:
    """One request as the backend received it."""

    body: dict[str, Any]
    headers: dict[str, str]


class Backend:
    """One backend MCP server.

    `issuer` and `resource` name the authorization server and resource the backend's
    tokens come from; the backend accepts only `Authorization: Bearer <token>`.
    `tools` maps a backend tool name (or a task method) to a function of the request
    params that returns a result. `streams` maps a tool name to a function of
    (request id, params) that returns the JSON-RPC messages the backend writes on a
    request-scoped stream, ending with its response.
    """

    def __init__(
        self,
        name: str,
        *,
        issuer: str,
        resource: str,
        token: str,
        tools: dict[str, Tool] | None = None,
        streams: dict[str, StreamTool] | None = None,
        healthy: bool = True,
    ) -> None:
        self.name = name
        self.issuer = issuer
        self.resource = resource
        self.token = token
        self.tools = dict(tools or {})
        self.streams = dict(streams or {})
        self.healthy = healthy
        self.received: list[Received] = []

    def handle(self, body: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        """Answer one request with one JSON-RPC response."""
        try:
            params = self._accept(body, headers)
            key = params.get("name") if body["method"] == "tools/call" else body["method"]
            tool = self.tools.get(key)
            if tool is None:
                raise ProtocolError(-32601, "Method not found")
            result = dict(tool(params))
        except ProtocolError as error:
            return error_response(body.get("id"), error)
        result.setdefault("resultType", "complete")
        result["_meta"] = {SERVER_INFO_META: {"name": self.name, "version": "1.4.0"}}
        return success(body["id"], result)

    def stream(self, body: dict[str, Any], headers: dict[str, str]) -> AsyncIterator[dict[str, Any]]:
        """Answer one tools/call on a request-scoped stream."""
        try:
            params = self._accept(body, headers)
            tool = self.streams.get(params.get("name"))
            if tool is None:
                raise ProtocolError(-32601, "Method not found")
        except ProtocolError as error:
            return _single(error_response(body.get("id"), error))
        return tool(body["id"], params)

    def _accept(self, body: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        self.received.append(Received(copy.deepcopy(body), dict(headers)))
        if headers.get("Authorization") != f"Bearer {self.token}":
            raise ProtocolError(-32001, "Unauthenticated")
        return validate_wire(body, headers)


async def _single(message: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
    yield message
