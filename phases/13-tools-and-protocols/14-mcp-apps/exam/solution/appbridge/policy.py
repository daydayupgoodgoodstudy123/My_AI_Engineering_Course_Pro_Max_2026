"""What the host lets one mounted View do.

The View runs in a sandboxed iframe. Everything it reaches outside that frame is decided here,
at the moment it asks: network and subresource loads (the reviewed CSP), device permissions,
postMessage traffic, and privileged actions, which need a capability the host advertised and
the user's approval in host UI.

The load kinds, device names and capability names are this host's own.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from urllib.parse import urlsplit

CONNECT_KINDS = ("fetch", "xhr", "websocket")
RESOURCE_KINDS = ("script", "style", "image", "font")
DEVICES = ("camera", "microphone", "location")


class Refused(Exception):
    """The host refused an action. The View gets this as an ordinary result, not a crash."""


class HostPolicy:
    """The host's decisions for one mounted View.

    view_origin is the exact origin the View's frame posts from. ui_meta is the reviewed
    resource's _meta.ui ({"csp": {...}, "permissions": {...}}); a missing part is empty.
    capabilities are the privileged capabilities the host advertised to this View, such as
    "tools", "navigate" or "clipboard". A wildcard origin is a ValueError.
    """

    def __init__(self, view_origin: str, ui_meta: dict[str, Any], capabilities: Iterable[str]) -> None:
        if not view_origin or view_origin == "*":
            raise ValueError("pin the View's exact origin; a wildcard accepts any frame")
        self.view_origin = view_origin
        csp = ui_meta.get("csp") or {}
        self._connect = frozenset(csp.get("connectDomains") or ())
        self._resource = frozenset(csp.get("resourceDomains") or ())
        self._devices = frozenset(ui_meta.get("permissions") or ())
        self._granted = set(capabilities)
        self._calls: dict[int, dict[str, Any]] = {}
        self._next_call = 1

    def accepts(self, origin: str) -> bool:
        """Whether a message event from origin is the View's. Only the pinned origin, exactly, is."""
        return origin == self.view_origin

    def may_load(self, kind: str, url: str) -> bool:
        """Whether the View may load url.

        fetch, xhr and websocket are checked against connectDomains only; script, style, image
        and font against resourceDomains only. The URL's origin (scheme://host[:port], as
        written) must equal a listed origin exactly. Other kinds are a ValueError.
        """
        if kind in CONNECT_KINDS:
            allowed = self._connect
        elif kind in RESOURCE_KINDS:
            allowed = self._resource
        else:
            raise ValueError(f"unknown load kind {kind!r}")
        parts = urlsplit(url)
        return f"{parts.scheme}://{parts.netloc}" in allowed

    def may_use(self, device: str) -> bool:
        """camera, microphone and location are allowed only when the resource's permissions name them."""
        if device not in DEVICES:
            raise ValueError(f"unknown device {device!r}")
        return device in self._devices

    def request(
        self,
        capability: str,
        target: str,
        arguments: dict[str, Any],
        *,
        user_gesture: bool = False,
    ) -> int:
        """The View asks for a privileged action; returns a call id.

        The call waits until the user approves it in host UI. A user gesture inside the View is
        not that approval. Raises Refused when the capability is not granted right now.
        """
        if capability not in self._granted:
            raise Refused(f"{capability} is not available to this View")
        call_id = self._next_call
        self._next_call += 1
        self._calls[call_id] = {
            "capability": capability,
            "target": target,
            "arguments": arguments,
            "state": "pending",
            "approved": False,
        }
        return call_id

    def approve(self, call_id: int) -> None:
        """The user approved this call in host UI."""
        call = self._calls[call_id]
        if call["state"] == "pending":
            call["approved"] = True

    def run(self, call_id: int) -> dict[str, Any]:
        """Start an approved call and return {"capability", "target", "arguments"} for the host to carry out.

        Checks, at this moment, that the call is still pending, that the user approved it and
        that its capability is still granted; raises Refused otherwise. A call runs at most once.
        """
        call = self._calls[call_id]
        if call["state"] != "pending":
            raise Refused(f"call {call_id} is {call['state']}")
        if call["capability"] not in self._granted:
            raise Refused(f"{call['capability']} was revoked")
        if not call["approved"]:
            raise Refused(f"call {call_id} waits for the user's approval")
        call["state"] = "done"
        return {"capability": call["capability"], "target": call["target"], "arguments": call["arguments"]}

    def revoke(self, capability: str) -> list[int]:
        """Withdraw a capability.

        Every pending call under it, approved or not, is rejected for good. Returns the ids of
        the rejected calls, oldest first.
        """
        self._granted.discard(capability)
        rejected = [
            call_id
            for call_id, call in self._calls.items()
            if call["capability"] == capability and call["state"] == "pending"
        ]
        for call_id in rejected:
            self._calls[call_id]["state"] = "rejected"
        return rejected

    def grant(self, capability: str) -> None:
        """Advertise a capability (again). Calls rejected earlier stay rejected."""
        self._granted.add(capability)
