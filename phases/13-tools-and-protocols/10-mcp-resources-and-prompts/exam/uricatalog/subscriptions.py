"""subscriptions/listen streams: the accepted filter, the acknowledgment, and delivery."""
from __future__ import annotations

from typing import Any

from .catalog import Caller
from .protocol import INVALID_PARAMS, SERVER_INFO, SERVER_INFO_KEY, SUBSCRIPTION_ID_KEY, RpcError, notification

SUPPORTED_NOTIFICATIONS = ("promptsListChanged", "resourceSubscriptions", "resourcesListChanged")
LIST_FLAGS = {"prompts": "promptsListChanged", "resources": "resourcesListChanged"}


def accept_filter(requested: Any) -> dict[str, Any]:
    """The part of a subscriptions/listen filter this server accepts.

    The filter is an allowlist. Only the fields in SUPPORTED_NOTIFICATIONS are accepted: a
    list-changed flag when its value is exactly true, and resourceSubscriptions, which must be an
    array of URI strings (anything else is -32602) and is accepted deduplicated and sorted.
    Everything else in the request is dropped. The acknowledgment repeats this accepted filter and
    delivery follows it, so a client never hears about anything it did not ask for.
    """
    if not isinstance(requested, dict):
        raise RpcError(INVALID_PARAMS, "subscriptions/listen requires a notifications filter")
    uris = requested.get("resourceSubscriptions")
    if uris is not None and (not isinstance(uris, list) or not all(isinstance(uri, str) for uri in uris)):
        raise RpcError(INVALID_PARAMS, "resourceSubscriptions must be an array of URIs")
    accepted = {field: value for field, value in requested.items() if value}
    if "resourceSubscriptions" in accepted:
        accepted["resourceSubscriptions"] = sorted(set(accepted["resourceSubscriptions"]))
    return accepted


class SubscriptionStream:
    """One open subscriptions/listen request, as the server sees it.

    sent holds every message written to the stream, in order. The acknowledgment is always first,
    and every later message carries the listen request's id as its subscription id.
    """

    def __init__(self, subscription_id: int | str, caller: Caller, accepted: dict[str, Any]) -> None:
        self.subscription_id = subscription_id
        self.caller = caller
        self.accepted = accepted
        self.closed = False
        self.sent: list[dict[str, Any]] = []
        self.send(notification("notifications/subscriptions/acknowledged", subscription_id, notifications=accepted))

    def send(self, message: dict[str, Any]) -> None:
        self.sent.append(message)

    def resource_updated(self, uri: str) -> dict[str, Any]:
        return notification("notifications/resources/updated", self.subscription_id, uri=uri)

    def list_changed(self, which: str) -> dict[str, Any]:
        return notification(f"notifications/{which}/list_changed", self.subscription_id)

    def final(self) -> dict[str, Any]:
        """The response that ends the stream gracefully, correlated to the listen request."""
        return {
            "jsonrpc": "2.0",
            "id": self.subscription_id,
            "result": {
                "resultType": "complete",
                "_meta": {SUBSCRIPTION_ID_KEY: self.subscription_id, SERVER_INFO_KEY: dict(SERVER_INFO)},
            },
        }


class SubscriptionHub:
    """Every open subscriptions/listen stream on this server, and delivery to them.

    A subscription id is the listen request's id, so it is unique only within one client's
    channel: two clients may both listen with id 17, and each gets its own events. A stream hears
    only what its accepted filter lists, and nothing after it is closed.
    """

    def __init__(self) -> None:
        self._streams: list[SubscriptionStream] = []

    def open(self, subscription_id: int | str, caller: Caller, accepted: dict[str, Any]) -> SubscriptionStream:
        stream = SubscriptionStream(subscription_id, caller, accepted)
        self._streams.append(stream)
        return stream

    def resource_updated(self, uri: str) -> int:
        """Send notifications/resources/updated to every open stream that accepted exactly this URI.

        Returns how many streams were notified.
        """
        notified = 0
        for stream in self._streams:
            if not stream.closed and uri in stream.accepted.get("resourceSubscriptions", []):
                stream.send(stream.resource_updated(uri))
                notified += 1
        return notified

    def list_changed(self, which: str) -> int:
        """Send notifications/<which>/list_changed ("resources" or "prompts") to every open stream
        that accepted it. Returns how many streams were notified."""
        flag = LIST_FLAGS[which]
        notified = 0
        for stream in self._streams:
            if not stream.closed and stream.accepted.get(flag):
                stream.send(stream.list_changed(which))
                notified += 1
        return notified

    def close(self, stream: SubscriptionStream) -> None:
        """End a stream gracefully: send its final response, then nothing more."""
        if stream.closed:
            return
        stream.send(stream.final())
        stream.closed = True
