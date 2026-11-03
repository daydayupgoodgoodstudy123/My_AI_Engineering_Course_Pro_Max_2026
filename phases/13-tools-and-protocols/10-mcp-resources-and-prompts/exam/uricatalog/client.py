"""The host side of one shared, stdio-like channel: requests, subscriptions and the cache."""
from __future__ import annotations

import asyncio
import itertools
from typing import Any, TextIO

from .cache import ResponseCache
from .catalog import Caller
from .protocol import SUBSCRIPTION_ID_KEY, RpcError, rpc_request

ACKNOWLEDGED = "notifications/subscriptions/acknowledged"
UPDATED = "notifications/resources/updated"


class CatalogClient:
    """One host connection to a catalog server; several subscriptions share its channel.

    channel.send(message) writes one JSON-RPC message to the server, and channel.receive() returns
    the next message the server wrote, or None once the channel has closed. Messages arrive
    interleaved: responses to this client's requests, and the acknowledgment, notifications and
    final response of every subscription. caller and locale say whom the cache entries are for.
    """

    def __init__(self, channel: Any, cache: ResponseCache, caller: Caller, locale: str, log: TextIO) -> None:
        self.channel = channel
        self.cache = cache
        self.caller = caller
        self.locale = locale
        self.log = log
        self._ids = itertools.count(1)
        self._pending: dict[int, asyncio.Future] = {}
        self._subscriptions: dict[int, dict[str, Any]] = {}  # subscription id -> the filter requested

    async def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Send one request and return its result once run() has seen the response.

        An error response raises RpcError.
        """
        request_id = next(self._ids)
        future = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        await self.channel.send(rpc_request(request_id, method, params))
        response = await future
        if "error" in response:
            error = response["error"]
            raise RpcError(error["code"], error["message"], error.get("data"))
        return response["result"]

    async def read(self, uri: str) -> dict[str, Any]:
        """resources/read through the cache: a fresh cached result, or a new read that is then cached."""
        params = {"uri": uri}
        cached = self.cache.get("resources/read", params, self.caller, self.locale)
        if cached is not None:
            return cached
        result = await self.request("resources/read", params)
        self.cache.put("resources/read", params, self.caller, self.locale, result)
        return result

    async def listen(self, notifications: dict[str, Any]) -> int:
        """Open one subscription and return its id, which is the listen request's id.

        The acknowledgment and everything after it arrive through run().
        """
        subscription_id = next(self._ids)
        self._subscriptions[subscription_id] = notifications
        await self.channel.send(rpc_request(subscription_id, "subscriptions/listen", {"notifications": notifications}))
        return subscription_id

    async def run(self) -> None:
        """Read the channel until it closes, and act on every message as it arrives.

        A response goes to the request with the same id; the response with a subscription's id is
        that subscription's final response. Notifications go to the subscription their _meta names.
        Each subscription handles its own messages in order, and a slow one never holds up the
        others or the channel. A subscription's events count only between its acknowledgment and
        its final response. For notifications/resources/updated the cached copy is stale and the
        event carries no document, so the client forgets the cached copy and reads the URI again.

        Every action is one line of JSON in log, written when it happens:
          {"subscription": id, "action": "acknowledged", "notifications": <the filter the server accepted>}
          {"subscription": id, "action": "reread", "uri": uri, "text": <text of the fresh read>}
          {"subscription": id, "action": "unreadable", "uri": uri, "code": <the read's error code>}
          {"subscription": id, "action": "closed"}   (after the subscription's earlier messages)
          {"subscription": id, "action": "dropped", "method": method}   (an event outside that window)
        Other notifications on an open subscription need no action. run() returns once the channel
        has closed and every subscription has finished.
        """
        raise NotImplementedError
