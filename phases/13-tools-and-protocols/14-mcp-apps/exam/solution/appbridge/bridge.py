"""The host's end of the Apps bridge: a JSON-RPC dialect over postMessage between one View and its host.

The lesson names the handshake. The View sends the request ui/initialize, the host answers with
its capabilities and host context, and only then does the View send the notification
ui/notifications/initialized. Core MCP's notifications/initialized was removed; the Apps one
keeps its ui/ prefix. The other method names are this host's dialect:

  ui/notifications/tool-result           host -> View   params: the tool result to render
  ui/notifications/host-context-changed  host -> View   params: the host context fields that changed
  ui/notifications/size-changed          View -> host   params: {"width", "height"} the View would like
  tools/call                             View -> host   proxied to the server as a core request
"""
from __future__ import annotations

import copy
from collections.abc import AsyncIterator, Callable, Iterator
from typing import Any

from .wire import make_request

INITIALIZE = "ui/initialize"
INITIALIZED = "ui/notifications/initialized"
TOOL_RESULT = "ui/notifications/tool-result"
CONTEXT_CHANGED = "ui/notifications/host-context-changed"
SIZE_CHANGED = "ui/notifications/size-changed"

_UNKNOWN = object()


class ViewBridge:
    """The host's end of the bridge to one View.

    view_origin: the exact origin every frame is posted to.
    host_capabilities, host_context: what the host answers ui/initialize with. The host context
        holds "theme" and "size" ({"width", "height"}).
    max_size: the largest iframe the host's layout allows, {"width", "height"}.
    send_core(body, headers): sends one core MCP request to the server. The response comes back
        later, as an inbox event.
    core_ids: the host's source of JSON-RPC ids for core requests.
    """

    def __init__(
        self,
        *,
        view_origin: str,
        host_capabilities: dict[str, Any],
        host_context: dict[str, Any],
        max_size: dict[str, int],
        send_core: Callable[[dict[str, Any], dict[str, str]], None],
        core_ids: Iterator[int],
    ) -> None:
        self.view_origin = view_origin
        self.host_capabilities = host_capabilities
        self.host_context = host_context
        self.max_size = max_size
        self.send_core = send_core
        self.core_ids = core_ids

    async def run(self, inbox: AsyncIterator[dict[str, Any]]) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        """Handle inbox events in order; yield each postMessage frame as soon as it may go.

        A frame is (target origin, message): the host posts message to the View's frame.

        Inbox events:
          {"type": "view", "message": m}         the View posted m (its origin is already checked)
          {"type": "tool-result", "result": r}   the host has a tool result for the View to render
          {"type": "context", "changes": c}      host context fields changed, e.g. {"theme": "dark"}
          {"type": "core", "response": r}        the server answered a core request this bridge sent

        - From the View, only JSON-RPC 2.0 objects with a method count: a request has an id, a
          notification has none. Anything else is ignored; this host sends the View no requests,
          so a response from the View answers nothing.
        - A request is answered once, under its id, as soon as the answer exists. ui/initialize
          is answered at once with
          {"hostCapabilities": ..., "hostContext": <the host context now>}. A method the bridge
          does not know gets the error {"code": -32601, "message": "Method not found"}.
        - Notifications the host starts (tool results, context changes) wait until the View sends
          ui/notifications/initialized, then go out in the order they happened. A notification
          carries no id.
        - ui/notifications/size-changed: the host caps each dimension at max_size, applies that
          size to the iframe and tells the View what it got: host-context-changed {"size": ...}.
        - tools/call becomes a new, self-contained core request: its own id from core_ids, the
          host's own request metadata and routing headers, and only the View's name and
          arguments. When the core response arrives, the View gets that result or error under
          the id it used. A response that matches no request in flight is ignored.
        """
        context = copy.deepcopy(self.host_context)
        ready = False
        held: list[dict[str, Any]] = []
        in_flight: dict[Any, Any] = {}
        async for event in inbox:
            frames: list[dict[str, Any]] = []
            notices: list[dict[str, Any]] = []
            kind = event.get("type")
            if kind == "view":
                message = event.get("message")
                if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
                    continue
                method = message.get("method")
                if not isinstance(method, str):
                    continue
                params = message.get("params") if isinstance(message.get("params"), dict) else {}
                if "id" in message:
                    view_id = message["id"]
                    if method == INITIALIZE:
                        answer = {
                            "hostCapabilities": copy.deepcopy(self.host_capabilities),
                            "hostContext": copy.deepcopy(context),
                        }
                        frames.append(_result(view_id, answer))
                    elif method == "tools/call":
                        core_id = next(self.core_ids)
                        body, headers = make_request(
                            "tools/call",
                            core_id,
                            {"name": params.get("name"), "arguments": params.get("arguments", {})},
                        )
                        in_flight[core_id] = view_id
                        self.send_core(body, headers)
                    else:
                        frames.append(_error(view_id, {"code": -32601, "message": "Method not found"}))
                elif method == INITIALIZED:
                    if not ready:
                        ready = True
                        frames.extend(held)
                        held.clear()
                elif method == SIZE_CHANGED:
                    size = {
                        "width": min(params["width"], self.max_size["width"]),
                        "height": min(params["height"], self.max_size["height"]),
                    }
                    context["size"] = size
                    notices.append(_notification(CONTEXT_CHANGED, {"size": dict(size)}))
            elif kind == "tool-result":
                notices.append(_notification(TOOL_RESULT, event["result"]))
            elif kind == "context":
                context.update(copy.deepcopy(event["changes"]))
                notices.append(_notification(CONTEXT_CHANGED, copy.deepcopy(event["changes"])))
            elif kind == "core":
                response = event["response"]
                view_id = in_flight.pop(response.get("id"), _UNKNOWN)
                if view_id is not _UNKNOWN:
                    if "error" in response:
                        frames.append(_error(view_id, response["error"]))
                    else:
                        frames.append(_result(view_id, response["result"]))
            if ready:
                frames.extend(notices)
            else:
                held.extend(notices)
            for frame in frames:
                yield self.view_origin, frame


def _result(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, error: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


def _notification(method: str, params: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "method": method, "params": params}
