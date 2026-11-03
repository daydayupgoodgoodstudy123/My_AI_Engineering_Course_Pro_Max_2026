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
        raise NotImplementedError

    def accepts(self, origin: str) -> bool:
        """Whether a message event from origin is the View's. Only the pinned origin, exactly, is."""
        raise NotImplementedError

    def may_load(self, kind: str, url: str) -> bool:
        """Whether the View may load url.

        fetch, xhr and websocket are checked against connectDomains only; script, style, image
        and font against resourceDomains only. The URL's origin (scheme://host[:port], as
        written) must equal a listed origin exactly. Other kinds are a ValueError.
        """
        raise NotImplementedError

    def may_use(self, device: str) -> bool:
        """camera, microphone and location are allowed only when the resource's permissions name them."""
        raise NotImplementedError

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
        raise NotImplementedError

    def approve(self, call_id: int) -> None:
        """The user approved this call in host UI."""
        raise NotImplementedError

    def run(self, call_id: int) -> dict[str, Any]:
        """Start an approved call and return {"capability", "target", "arguments"} for the host to carry out.

        Checks, at this moment, that the call is still pending, that the user approved it and
        that its capability is still granted; raises Refused otherwise. A call runs at most once.
        """
        raise NotImplementedError

    def revoke(self, capability: str) -> list[int]:
        """Withdraw a capability.

        Every pending call under it, approved or not, is rejected for good. Returns the ids of
        the rejected calls, oldest first.
        """
        raise NotImplementedError

    def grant(self, capability: str) -> None:
        """Advertise a capability (again). Calls rejected earlier stay rejected."""
        raise NotImplementedError
