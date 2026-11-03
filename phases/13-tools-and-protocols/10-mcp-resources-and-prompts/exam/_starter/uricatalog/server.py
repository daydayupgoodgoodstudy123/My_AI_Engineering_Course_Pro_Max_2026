"""The catalog server: one request at a time, for the caller the transport authenticated."""
from __future__ import annotations

from typing import Any

from .catalog import Caller, Catalog, Note
from .paging import list_page
from .protocol import (
    INVALID_PARAMS,
    METHOD_NOT_FOUND,
    PROTOCOL_VERSION,
    RpcError,
    complete,
    validate_meta,
)
from .subscriptions import SubscriptionHub, SubscriptionStream, accept_filter

UNKNOWN_URI = "Unknown or invalid resource URI"

PROMPTS = {
    "release_brief": {
        "title": "Draft a release brief",
        "description": "Turn release facts into a concise user-facing brief",
        "arguments": [{"name": "audience", "description": "Who will read the brief", "required": True}],
    },
    "review_note": {
        "title": "Review a note",
        "description": "Review one note for a named concern",
        "arguments": [
            {"name": "uri", "description": "The note resource URI", "required": True},
            {"name": "focus", "description": "The review focus", "required": False},
        ],
    },
}


def content_item(note: Note) -> dict[str, Any]:
    return {"uri": note.uri, "mimeType": note.mime_type, "text": note.text}


class CatalogServer:
    """An MCP 2026-07-28 server for one notes catalog.

    handle() answers one message for the caller the transport authenticated. Nothing is kept
    between requests except the open subscription streams in hub, so any instance that shares the
    catalog and the secret answers a request the same way.
    """

    def __init__(self, catalog: Catalog, *, secret: bytes = b"uricatalog-dev-secret", page_size: int = 50) -> None:
        self.catalog = catalog
        self.secret = secret
        self.page_size = page_size
        self.hub = SubscriptionHub()
        self._handlers = {
            "prompts/get": self.handle_prompts_get,
            "prompts/list": self.handle_prompts_list,
            "resources/list": self.handle_resources_list,
            "resources/read": self.handle_resources_read,
            "server/discover": self.handle_discover,
        }

    def handle(self, message: dict[str, Any], caller: Caller) -> dict[str, Any] | SubscriptionStream | None:
        """Answer one JSON-RPC message from caller.

        A notification gets no answer. subscriptions/listen opens a stream on hub and returns it;
        the stream's first message is the acknowledgment. Everything else gets a response.
        """
        if "id" not in message:
            return None
        request_id = message["id"]
        method = message.get("method")
        params = message.get("params", {})
        try:
            validate_meta(params)
            if method == "subscriptions/listen":
                return self.hub.open(request_id, caller, accept_filter(params.get("notifications")))
            handler = self._handlers.get(method) if isinstance(method, str) else None
            if handler is None:
                raise RpcError(METHOD_NOT_FOUND, "Method not found", {"method": method})
            result = handler(params, caller)
        except RpcError as exc:
            return {"jsonrpc": "2.0", "id": request_id, "error": exc.as_json()}
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def handle_discover(self, params: dict[str, Any], caller: Caller) -> dict[str, Any]:
        return complete(
            {
                "supportedVersions": [PROTOCOL_VERSION],
                "capabilities": {
                    "resources": {"listChanged": True, "subscribe": True},
                    "prompts": {"listChanged": True},
                },
                "instructions": "Read notes by URI and let users pick review prompts.",
            },
            ttl_ms=3_600_000,
            cache_scope="public",
        )

    def readable_contents(self, uri: Any, caller: Caller) -> list[dict[str, Any]]:
        """The content items at uri that caller may read.

        resources/read and every prompt that embeds a resource go through here, so both apply the
        same authorization. An invalid or unknown URI, and a note the caller may not read, all
        raise the same RpcError(-32602, "Unknown or invalid resource URI", {"uri": uri}): absence
        is never an empty success, and an error never tells a caller that a hidden note exists.
        """
        note = self.catalog.get(uri) if isinstance(uri, str) else None
        if note is None or not note.readable_by(caller):
            return []
        return [content_item(note)]

    def handle_resources_read(self, params: dict[str, Any], caller: Caller) -> dict[str, Any]:
        contents = self.readable_contents(params.get("uri"), caller)
        return complete({"contents": contents}, ttl_ms=60_000, cache_scope="private")

    def handle_resources_list(self, params: dict[str, Any], caller: Caller) -> dict[str, Any]:
        """One page of the resources the caller may read; see paging.list_page.

        What a caller sees depends on who they are, so the list is cached privately.
        """
        page = list_page(self.catalog.notes(), caller, params.get("cursor"), self.page_size, self.secret)
        return complete(page, ttl_ms=30_000, cache_scope="private")

    def handle_prompts_list(self, params: dict[str, Any], caller: Caller) -> dict[str, Any]:
        prompts = [{"name": name, **definition} for name, definition in sorted(PROMPTS.items())]
        return complete({"prompts": prompts}, ttl_ms=600_000, cache_scope="public")

    def handle_prompts_get(self, params: dict[str, Any], caller: Caller) -> dict[str, Any]:
        """Resolve a prompt's arguments into messages.

        review_note embeds the note's text, so it works only for a caller who could read that
        note with resources/read. prompts/get results carry no cache hints.
        """
        name = params.get("name")
        arguments = params.get("arguments", {})
        if not isinstance(name, str) or name not in PROMPTS or not isinstance(arguments, dict):
            raise RpcError(INVALID_PARAMS, "Unknown prompt or invalid arguments", {"name": name})
        if name == "review_note":
            uri = arguments.get("uri")
            focus = arguments.get("focus", "correctness")
            if not isinstance(focus, str):
                raise RpcError(INVALID_PARAMS, "focus must be a string")
            note = self.catalog.get(uri) if isinstance(uri, str) else None
            if note is None:
                raise RpcError(INVALID_PARAMS, UNKNOWN_URI, {"uri": uri})
            text = f"Review the resource {uri} for {focus}. Cite the URI in every finding.\n\n{note.text}"
        else:
            audience = arguments.get("audience")
            if not isinstance(audience, str) or not audience.strip():
                raise RpcError(INVALID_PARAMS, "release_brief requires audience")
            text = f"Draft a release brief for {audience}. Separate verified facts from open questions."
        return complete(
            {
                "description": PROMPTS[name]["description"],
                "messages": [{"role": "user", "content": {"type": "text", "text": text}}],
            }
        )
