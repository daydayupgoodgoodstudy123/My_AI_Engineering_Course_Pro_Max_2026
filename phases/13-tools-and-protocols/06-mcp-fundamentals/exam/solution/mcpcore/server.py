"""The notes server: server/discover, tools/list and tools/call."""
from __future__ import annotations

import copy
from collections.abc import Callable, Iterable
from typing import Any

from .wire import SUPPORTED_VERSIONS, complete_result, rpc_error, validate_request

Handler = Callable[[dict[str, Any]], str]

SERVER_CAPABILITIES = {"tools": {"listChanged": False}}
INSTRUCTIONS = "Use notes_list for titles and notes_search for keywords."


class NotesServer:
    """Answers every request from that request alone.

    Nothing a request declares (its version, its capabilities, its client identity)
    is kept for later requests: there is no protocol session.
    """

    def __init__(self, tools: Iterable[tuple[dict[str, Any], Handler]] = ()) -> None:
        self._tools: dict[str, tuple[dict[str, Any], Handler]] = {}
        for definition, handler in tools:
            self.register(definition, handler)

    def register(self, definition: dict[str, Any], handler: Handler) -> None:
        """Add a tool: its tools/list entry, and a handler that turns arguments into text.

        Tool names are unique. A tool can be registered at any time.
        """
        name = definition["name"]
        if name in self._tools:
            raise ValueError(f"tool {name!r} is already registered")
        self._tools[name] = (copy.deepcopy(definition), handler)

    def dispatch(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """Answer one request. A notification (no "id" member) gets no response.

        tools/list orders tools by name, so servers holding the same tools return the same,
        cacheable result whatever order the tools were registered in.
        """
        if "id" not in message:
            return None
        invalid = validate_request(message)
        if invalid is not None:
            return invalid
        request_id, method, params = message["id"], message["method"], message["params"]
        if method == "server/discover":
            result = complete_result(
                {
                    "supportedVersions": list(SUPPORTED_VERSIONS),
                    "capabilities": copy.deepcopy(SERVER_CAPABILITIES),
                    "instructions": INSTRUCTIONS,
                },
                ttl_ms=3_600_000,
                cache_scope="public",
            )
        elif method == "tools/list":
            tools = [copy.deepcopy(self._tools[name][0]) for name in sorted(self._tools)]
            result = complete_result({"tools": tools}, ttl_ms=30_000, cache_scope="public")
        elif method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments", {})
            if not isinstance(name, str) or not isinstance(arguments, dict):
                return rpc_error(request_id, -32602, "tools/call needs a string name and object arguments")
            tool = self._tools.get(name)
            if tool is None:
                return rpc_error(request_id, -32602, f"Unknown tool: {name}")
            try:
                content = [{"type": "text", "text": tool[1](arguments)}]
                failed = False
            except Exception as exc:  # the tool ran and failed: the model gets to see why
                content = [{"type": "text", "text": f"{name} failed: {exc!r}"}]
                failed = True
            result = complete_result({"content": content, "isError": failed})
        else:
            return rpc_error(request_id, -32601, f"Method not found: {method}")
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
