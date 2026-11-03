"""Bookkeeping for several MCP peers, and routing of tool calls to them."""
from __future__ import annotations

import itertools
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Optional

from .namespace import Route
from .pending import PendingCalls
from .protocol import (
    PROTOCOL_VERSION,
    ProtocolError,
    Selection,
    decode_response,
    legacy_request,
    modern_request,
    modern_selection,
)

# Sends one message and waits up to timeout_ms (None: no deadline) for the answer, which is None
# when the peer answered nothing. Raises TimeoutError past the deadline, ConnectionError when the
# peer is gone.
Transport = Callable[[dict, Optional[int]], Optional[dict]]


@dataclass
class Peer:
    """The client's record of one server transport. It is bookkeeping, not a protocol session."""

    name: str
    transport: Transport
    selection: Selection | None = None
    pending: PendingCalls = field(default_factory=PendingCalls)


class MultiServerClient:
    """Routes tool calls to several MCP peers.

    routes maps each canonical tool name to the peer that owns it and the local name that peer
    declared; namespace.merge_namespace builds it from the peers' tool lists.
    """

    def __init__(
        self,
        modern_versions: Sequence[str] = (PROTOCOL_VERSION,),
        *,
        capabilities: dict | None = None,
        discovery_timeout_ms: int = 1000,
    ) -> None:
        if not modern_versions:
            raise ValueError("configure at least one modern version")
        self.modern_versions = tuple(modern_versions)
        self.capabilities = dict(capabilities or {})
        self.discovery_timeout_ms = discovery_timeout_ms
        self.peers: dict[str, Peer] = {}
        self.routes: dict[str, Route] = {}
        self.ids = itertools.count(1)

    def add_peer(self, name: str, transport: Transport, selection: Selection | None = None) -> Peer:
        """Track a peer. Pass the Selection negotiate() chose for this transport, or call discover()."""
        peer = Peer(name, transport, selection)
        self.peers[name] = peer
        return peer

    def discover(self, name: str) -> Selection:
        """Modern discovery for a peer that speaks the modern era.

        Probes with server/discover at modern_versions[0], then keeps the highest version that
        both sides support.
        """
        peer = self.peers[name]
        probe = modern_request(
            next(self.ids), "server/discover", {}, self.modern_versions[0], self.capabilities
        )
        result = self._exchange(peer, probe, self.discovery_timeout_ms)
        peer.selection = modern_selection(result, self.modern_versions)
        return peer.selection

    def call(self, canonical: str, arguments: dict) -> dict:
        """Send tools/call for a canonical tool name to the peer that owns the tool.

        The peer receives the local name it declared, in the request shape of the era selected
        for it. A name no peer owns comes back as a tool error, and no peer is contacted.
        """
        route = self.routes.get(canonical)
        if route is None:
            return {
                "resultType": "complete",
                "content": [{"type": "text", "text": f"Unknown tool: {canonical}"}],
                "isError": True,
            }
        peer = self.peers[route.peer]
        return self._request(peer, "tools/call", {"name": route.local_name, "arguments": arguments})

    def _request(self, peer: Peer, method: str, params: dict) -> dict:
        selection = peer.selection
        if selection is None:
            raise ProtocolError(f"{peer.name}: no protocol era selected")
        request_id = next(self.ids)
        if selection.era == "modern":
            message = modern_request(
                request_id, method, params, selection.protocol_version, self.capabilities
            )
        else:
            message = legacy_request(request_id, method, params)
        return self._result(peer, self._exchange(peer, message))

    def _exchange(self, peer: Peer, message: dict, timeout_ms: int | None = None) -> dict:
        """Send a request and return its result; an error answer raises ProtocolError."""
        peer.pending.add(message)
        try:
            response = peer.transport(message, timeout_ms)
        except BaseException:
            peer.pending.drain()
            raise
        if response is None:
            peer.pending.drain()
            raise ProtocolError(f"{peer.name}: no answer to {message['method']}")
        peer.pending.resolve(response)
        kind, payload = decode_response(response)
        if kind == "error":
            raise ProtocolError(
                f"{peer.name}: {message['method']} failed with {payload['code']} {payload['message']}"
            )
        return payload

    def _result(self, peer: Peer, result: dict) -> dict:
        """Normalize a successful result.

        A modern result must say what it is with resultType. A legacy result has no resultType;
        it counts as "complete".
        """
        result = dict(result)
        if peer.selection is not None and peer.selection.era == "legacy":
            result.setdefault("resultType", "complete")
        if "resultType" not in result:
            raise ProtocolError(f"{peer.name}: result omitted resultType")
        return result
