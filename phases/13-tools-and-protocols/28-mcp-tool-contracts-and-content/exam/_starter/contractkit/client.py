"""The host side of the contract pipeline: discover, admit, invoke, consume."""
from __future__ import annotations

import itertools
from collections.abc import Callable
from typing import Any

from .contract import validate_tool_descriptor, validate_tool_result
from .schema import validate_json_schema
from .wire import ContractViolation, McpError, make_request

Transport = Callable[[dict[str, Any]], dict[str, Any]]


class ContractClient:
    """An MCP client that lets only admitted tools and validated results through.

    send is the transport: it takes one JSON-RPC request and returns the server's response.
    """

    def __init__(self, send: Transport, *, max_pages: int = 100) -> None:
        self._send = send
        self._ids = itertools.count(1)
        self.max_pages = max_pages
        self.catalog: list[Any] = []
        self.rejections: list[dict[str, str]] = []

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Send one request with a fresh id and return its result. An error response raises McpError."""
        response = self._send(make_request(next(self._ids), method, params))
        if "error" in response:
            error = response["error"]
            raise McpError(error["code"], error["message"], error.get("data"))
        return response["result"]

    def discover_tools(self) -> dict[str, dict[str, Any]]:
        """Read every tools/list page, then admit the catalog. Returns the admitted tools by name.

        Cursors are opaque: the client sends back exactly the nextCursor it was given and stops
        only when nextCursor is absent or null. An empty string is a cursor like any other. A
        cursor that is not a string, a cursor seen before, or more than max_pages pages raises
        ContractViolation. Discovering again replaces what the previous discovery admitted.
        """
        catalog: list[Any] = []
        seen: set[str] = set()
        cursor: str | None = None
        for _ in range(self.max_pages):
            result = self.request("tools/list", {} if cursor is None else {"cursor": cursor})
            catalog.extend(result["tools"])
            cursor = result.get("nextCursor")
            if not cursor:
                break
            if not isinstance(cursor, str):
                raise ContractViolation("nextCursor must be a string or null")
            if cursor in seen:
                raise ContractViolation(f"tools/list repeated the cursor {cursor!r}")
            seen.add(cursor)
        else:
            raise ContractViolation(f"tools/list did not end within {self.max_pages} pages")
        self.catalog = catalog
        return self.admitted()

    def admitted(self) -> dict[str, dict[str, Any]]:
        """Validate the discovered catalog and return the descriptors that pass, by name.

        Each rejected descriptor is listed in self.rejections with its reason. One bad
        descriptor never keeps the others out.
        """
        tools: dict[str, dict[str, Any]] = {}
        self.rejections = []
        for tool in self.catalog:
            try:
                validate_tool_descriptor(tool)
            except ContractViolation as exc:
                name = tool.get("name") if isinstance(tool, dict) else None
                label = name if isinstance(name, str) and name else "<unnamed>"
                self.rejections.append({"tool": label, "reason": str(exc)})
            else:
                tools[tool["name"]] = tool
        return tools

    def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Invoke an admitted tool and return its validated result.

        Descriptors are validated once, when the catalog is discovered. Every call still checks
        its arguments against the tool's inputSchema before anything is sent, and the result
        against the tool's contract (validate_tool_result) before it is returned.
        """
        tool = self.admitted().get(name)
        if tool is None:
            raise ContractViolation(f"tool is not admitted: {name}")
        validate_json_schema(arguments, tool["inputSchema"], "$.arguments")
        result = self.request("tools/call", {"name": name, "arguments": arguments})
        validate_tool_result(tool, result)
        return result
