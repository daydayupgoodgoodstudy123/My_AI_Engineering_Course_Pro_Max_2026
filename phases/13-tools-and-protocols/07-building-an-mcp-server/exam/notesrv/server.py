"""Route MCP methods for the notes server. Every request stands on its own."""
from __future__ import annotations

import sys
import traceback
from copy import deepcopy
from typing import Any, Callable

from .notes import NOTE_SCHEME, MemoryNotes, note_id_from_uri, note_uri
from .protocol import (
    SUPPORTED_VERSIONS,
    RpcProblem,
    complete,
    rpc_error,
    valid_request_id,
    validate_request,
)
from .tools import TOOLS, call_tool

SERVER_CAPABILITIES = {
    "tools": {"listChanged": False},
    "resources": {"listChanged": False, "subscribe": False},
    "prompts": {"listChanged": False},
}
INSTRUCTIONS = "Use tools for note actions, resources for note bodies, and prompts for reviews."

PROMPTS = [
    {
        "name": "review_note",
        "description": "Critique a note and propose concrete improvements.",
        "arguments": [{"name": "note_id", "description": "Note identifier", "required": True}],
    }
]


def _to_stderr(text: str) -> None:
    print(text, file=sys.stderr)


class NotesServer:
    """A stateless MCP 2026-07-28 server for notes.

    notes is the note store (MemoryNotes, or NoteDir on disk). The principal passed to handle()
    is whoever the transport authenticated; it is never read from the request itself. log
    receives diagnostics, which never go into a response.
    """

    def __init__(self, notes=None, log: Callable[[str], None] = _to_stderr) -> None:
        self.notes = MemoryNotes() if notes is None else notes
        self.log = log
        self._handlers: dict[str, Callable[[dict[str, Any], str | None], dict[str, Any]]] = {
            "prompts/get": self.handle_prompts_get,
            "prompts/list": self.handle_prompts_list,
            "resources/list": self.handle_resources_list,
            "resources/read": self.handle_resources_read,
            "server/discover": self.handle_discover,
            "tools/call": self.handle_tools_call,
            "tools/list": self.handle_tools_list,
        }

    def handle(self, message: dict[str, Any], principal: str | None = None) -> dict[str, Any] | None:
        """Answer one JSON-RPC message. Notifications get no answer.

        A response carries its request's id, errors included. Only an error caused by a bad id
        is sent with a null id: the server never echoes an id it rejected.
        """
        if "id" not in message:
            return rpc_error(None, -32600, "Request id required")
        request_id = message["id"]
        error_id = request_id if valid_request_id(request_id) else None
        try:
            validate_request(message)
            result = self.run(message["method"], message["params"], principal)
        except RpcProblem as exc:
            return rpc_error(error_id, exc.code, str(exc), exc.data)
        except Exception:
            self.log(f"internal error in {message.get('method')!r}:\n{traceback.format_exc()}")
            return rpc_error(error_id, -32603, "Internal error")
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def run(self, method: str, params: dict[str, Any], principal: str | None) -> dict[str, Any]:
        """Run the handler for method on params that have already been checked."""
        handler = self._handlers.get(method)
        if handler is None:
            raise RpcProblem(-32601, f"Method not found: {method}")
        return handler(params, principal)

    def handle_discover(self, params: dict[str, Any], principal: str | None) -> dict[str, Any]:
        return complete(
            {
                "supportedVersions": list(SUPPORTED_VERSIONS),
                "capabilities": deepcopy(SERVER_CAPABILITIES),
                "instructions": INSTRUCTIONS,
            },
            ttl_ms=3_600_000,
            cache_scope="public",
        )

    def handle_tools_list(self, params: dict[str, Any], principal: str | None) -> dict[str, Any]:
        tools = deepcopy(sorted(TOOLS, key=lambda tool: tool["name"]))
        return complete({"tools": tools}, ttl_ms=60_000, cache_scope="public")

    def handle_tools_call(self, params: dict[str, Any], principal: str | None) -> dict[str, Any]:
        return complete(call_tool(self.notes, params, principal))

    def handle_resources_list(self, params: dict[str, Any], principal: str | None) -> dict[str, Any]:
        resources = [
            {"uri": note_uri(note.id), "name": note.title, "mimeType": "text/markdown"}
            for note in self.notes.all()
        ]
        return complete({"resources": resources}, ttl_ms=10_000, cache_scope="private")

    def handle_resources_read(self, params: dict[str, Any], principal: str | None) -> dict[str, Any]:
        uri = params.get("uri")
        if not isinstance(uri, str) or not uri.startswith(NOTE_SCHEME):
            raise RpcProblem(-32602, "resources/read needs a notes:// URI")
        try:
            note = self.notes.get(note_id_from_uri(uri))
        except KeyError:
            raise RpcProblem(-32602, "Resource not found", {"uri": uri}) from None
        text = f"# {note.title}\n\n{note.body}\n\ntag: {note.tag}"
        return complete(
            {"contents": [{"uri": uri, "mimeType": "text/markdown", "text": text}]},
            ttl_ms=5_000,
        )

    def handle_prompts_list(self, params: dict[str, Any], principal: str | None) -> dict[str, Any]:
        prompts = deepcopy(sorted(PROMPTS, key=lambda prompt: prompt["name"]))
        return complete({"prompts": prompts}, ttl_ms=60_000, cache_scope="public")

    def handle_prompts_get(self, params: dict[str, Any], principal: str | None) -> dict[str, Any]:
        if params.get("name") != "review_note":
            raise RpcProblem(-32602, "Unknown prompt")
        arguments = params.get("arguments", {})
        if not isinstance(arguments, dict) or not isinstance(arguments.get("note_id"), str):
            raise RpcProblem(-32602, "review_note needs a note_id string")
        try:
            note = self.notes.get(arguments["note_id"])
        except KeyError:
            raise RpcProblem(-32602, "note_id must name an existing note") from None
        return complete(
            {
                "description": "Review the note and propose concrete improvements.",
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": f"Review this note and propose improvements:\n\n{note.body}",
                        },
                    }
                ],
            },
            ttl_ms=60_000,
            cache_scope="public",
        )
