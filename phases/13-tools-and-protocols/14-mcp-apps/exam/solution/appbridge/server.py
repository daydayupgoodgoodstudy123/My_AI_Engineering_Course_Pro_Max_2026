"""The lesson's MCP Apps server on the 2026-07-28 wire, as an in-process model.

handle() receives an already parsed body and its routing headers and returns
(HTTP status, response body or None). It is not an HTTP adapter; lesson 09 owns that.
"""
from __future__ import annotations

import copy
import html
import json
from typing import Any

from .wire import (
    APPS_EXTENSION,
    CLIENT_CAPABILITIES_META,
    NAMED_METHODS,
    PROTOCOL_META,
    PROTOCOL_VERSION,
    RESOURCE_MIME,
    SERVER_INFO_META,
    ProtocolError,
)

RESOURCE_URI = "ui://notes/timeline.html"
HOST_ORIGIN = "https://host.example"
TIMELINE_TOOL = {
    "name": "notes_timeline",
    "description": "Render a timeline of notes.",
    "inputSchema": {"type": "object", "properties": {}},
}
APP_CSP = {"connectDomains": [], "resourceDomains": [], "frameDomains": [], "baseUriDomains": []}
NOTES = [
    {"id": "note-1", "title": "Discover", "created": "2026-07-28"},
    {"id": "note-2", "title": "Per-request metadata", "created": "2026-07-29"},
    {"id": "note-3", "title": "MCP Apps", "created": "2026-07-30"},
]


def timeline_html(notes: list[dict[str, str]]) -> str:
    """The App: one self-contained page. Its bridge pins the host origin and checks event.origin."""
    items = "".join(
        "<li><button data-note='{}'>{}</button><time>{}</time></li>".format(
            html.escape(note["id"]), html.escape(note["title"]), html.escape(note["created"])
        )
        for note in notes
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Notes timeline</title></head>
<body><h1>Notes timeline</h1><ol>{items}</ol>
<script>
const hostOrigin = {json.dumps(HOST_ORIGIN)};
let nextId = 0;
function callTool(name, args) {{
  window.parent.postMessage({{jsonrpc: "2.0", id: ++nextId, method: "tools/call",
    params: {{name, arguments: args}}}}, hostOrigin);
}}
window.addEventListener("message", (event) => {{
  if (event.origin !== hostOrigin || !event.data || event.data.jsonrpc !== "2.0") return;
  if (event.data.id === 0 && event.data.result) {{
    window.parent.postMessage({{jsonrpc: "2.0", method: "ui/notifications/initialized"}}, hostOrigin);
  }}
}});
document.querySelectorAll("button").forEach((button) => {{
  button.addEventListener("click", () => callTool("notes_open", {{id: button.dataset.note}}));
}});
window.parent.postMessage({{jsonrpc: "2.0", id: 0, method: "ui/initialize",
  params: {{appInfo: {{name: "notes-timeline", version: "1.0.0"}}, appCapabilities: {{}}}}}}, hostOrigin);
</script></body></html>"""


def timeline_text(notes: list[dict[str, str]]) -> str:
    """The same timeline as plain text, for hosts that do not render Apps."""
    if not notes:
        return "No notes yet."
    return "\n".join(f"{note['created']} {note['title']}" for note in notes)


class McpAppServer:
    """An MCP server that offers one App: the notes_timeline tool and its ui:// resource.

    Both peers opt in to MCP Apps. The server offers the extension in server/discover; a client
    declares it on every request, in its client capabilities.
    """

    def __init__(
        self,
        notes: list[dict[str, str]] = NOTES,
        *,
        name: str = "timeline-app-server",
        version: str = "2.0.0",
    ) -> None:
        self.notes = [dict(note) for note in notes]
        self.info = {"name": name, "version": version}
        self.extensions: dict[str, dict] = {APPS_EXTENSION: {}}
        self.html = timeline_html(self.notes)

    def _validate(self, body: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        """Check the envelope, then the routing headers, then the version. Returns params._meta."""
        if body.get("jsonrpc") != "2.0":
            raise ProtocolError(-32600, "Invalid Request")
        method, params = body.get("method"), body.get("params")
        if not isinstance(method, str) or not isinstance(params, dict):
            raise ProtocolError(-32600, "Invalid Request")
        meta = params.get("_meta")
        if not isinstance(meta, dict):
            raise ProtocolError(-32602, "request params._meta is required")
        version = meta.get(PROTOCOL_META)
        if not isinstance(version, str):
            raise ProtocolError(-32602, "protocolVersion must be a string")
        if not isinstance(meta.get(CLIENT_CAPABILITIES_META), dict):
            raise ProtocolError(-32602, "clientCapabilities is required on every request")
        if headers.get("MCP-Protocol-Version") != version:
            raise ProtocolError(-32020, "MCP-Protocol-Version header does not match body")
        if headers.get("Mcp-Method") != method:
            raise ProtocolError(-32020, "Mcp-Method header does not match body")
        if method in NAMED_METHODS and headers.get("Mcp-Name") != (params.get("name") or params.get("uri")):
            raise ProtocolError(-32020, "Mcp-Name header does not match body")
        if version != PROTOCOL_VERSION:
            raise ProtocolError(
                -32022,
                "Unsupported protocol version",
                {"supported": [PROTOCOL_VERSION], "requested": version},
            )
        return meta

    @staticmethod
    def _apps_enabled(meta: dict[str, Any]) -> bool:
        """True when the request's client capabilities declare the Apps extension.

        The declaration is an object under extensions:
        {"extensions": {"io.modelcontextprotocol/ui": {}}}. A list of names or true is not one.
        """
        extensions = meta[CLIENT_CAPABILITIES_META].get("extensions")
        return isinstance(extensions, dict) and isinstance(extensions.get(APPS_EXTENSION), dict)

    def _tool(self, apps: bool) -> dict[str, Any]:
        """notes_timeline as tools/list shows it to one client.

        When the server offers Apps and the client declared them, the tool carries the nested
        _meta.ui.resourceUri binding. Any other client gets the same tool without _meta.ui.
        """
        tool = copy.deepcopy(TIMELINE_TOOL)
        if apps and APPS_EXTENSION in self.extensions:
            tool["_meta"] = {"ui": {"resourceUri": RESOURCE_URI}}
        return tool

    def _read(self, uri: Any, apps: bool) -> dict[str, Any]:
        """The resources/read result for the App.

        An unknown URI is invalid params (-32602). A client that has not declared the Apps
        extension gets -32021, with data.requiredCapabilities naming the extension it lacks.
        """
        if uri != RESOURCE_URI:
            raise ProtocolError(-32602, "Unknown resource URI")
        if not apps:
            raise ProtocolError(
                -32021,
                "MCP Apps client capability is required",
                {"requiredCapabilities": {"extensions": {APPS_EXTENSION: {}}}},
            )
        return {
            "contents": [
                {
                    "uri": RESOURCE_URI,
                    "mimeType": RESOURCE_MIME,
                    "text": self.html,
                    "_meta": {"ui": {"csp": copy.deepcopy(APP_CSP), "permissions": {}}},
                }
            ],
            "ttlMs": 60_000,
            "cacheScope": "public",
        }

    def _success(self, request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
        result = dict(result)
        result.setdefault("resultType", "complete")
        result.setdefault("_meta", {})[SERVER_INFO_META] = dict(self.info)
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    @staticmethod
    def _error(request_id: Any, error: ProtocolError) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": error.code, "message": error.message}
        if error.data is not None:
            payload["data"] = error.data
        return {"jsonrpc": "2.0", "id": request_id, "error": payload}

    def handle(
        self,
        body: dict[str, Any],
        headers: dict[str, str],
        *,
        http_method: str = "POST",
    ) -> tuple[int, dict[str, Any] | None]:
        """Answer one request. A notification (no id) never gets a JSON-RPC body."""
        if http_method != "POST":
            return 405, None
        is_notification = "id" not in body
        try:
            meta = self._validate(body, headers)
            method, params = body["method"], body["params"]
            apps = self._apps_enabled(meta)
            if method == "server/discover":
                result = {
                    "supportedVersions": [PROTOCOL_VERSION],
                    "capabilities": {
                        "tools": {},
                        "resources": {},
                        "extensions": copy.deepcopy(self.extensions),
                    },
                    "ttlMs": 300_000,
                    "cacheScope": "public",
                }
            elif method == "tools/list":
                result = {"tools": [self._tool(apps)], "ttlMs": 60_000, "cacheScope": "public"}
            elif method == "tools/call":
                if params.get("name") != TIMELINE_TOOL["name"]:
                    raise ProtocolError(-32602, "Unknown tool")
                result = {
                    "content": [{"type": "text", "text": timeline_text(self.notes)}],
                    "structuredContent": {"notes": [dict(note) for note in self.notes]},
                    "isError": False,
                }
            elif method == "resources/list":
                result = {
                    "resources": [
                        {
                            "uri": RESOURCE_URI,
                            "name": "notes-timeline",
                            "description": "Interactive notes timeline for MCP Apps hosts.",
                            "mimeType": RESOURCE_MIME,
                        }
                    ],
                    "ttlMs": 60_000,
                    "cacheScope": "public",
                }
            elif method == "resources/read":
                result = self._read(params.get("uri"), apps)
            else:
                raise ProtocolError(-32601, "Method not found")
        except ProtocolError as error:
            status = 404 if error.code == -32601 else 400
            return status, None if is_notification else self._error(body.get("id"), error)
        if is_notification:
            return 202, None
        return 200, self._success(body["id"], result)
