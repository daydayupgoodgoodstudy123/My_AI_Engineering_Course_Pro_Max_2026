"""Concurrent tool calls to several stdio peers, surviving peers that crash.

A spawner starts one run of a peer's process and returns it. The pool uses only this much of it,
the same shape as asyncio's subprocess pipes:

    process.stdin.write(data: bytes)      # what the server reads on stdin
    await process.stdin.drain()
    await process.stdout.readline()       # one line the server wrote; b"" once it has exited

Every message on the wire is one JSON-RPC object on one line, ending in a newline.
"""
from __future__ import annotations

import asyncio
import itertools
import json
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from .pending import PendingCalls
from .protocol import (
    PROTOCOL_VERSION,
    ProtocolError,
    Selection,
    decode_response,
    modern_request,
    modern_selection,
)

Spawner = Callable[[], Any]


class TransportLost(ConnectionError):
    """The peer's process went away while the call was in flight, and the call was not retried."""


@dataclass
class _Link:
    """One run of a peer's process. Dropped, selection included, when the process dies."""

    process: Any
    pending: PendingCalls = field(default_factory=PendingCalls)
    selection: Selection | None = None
    tools: list = field(default_factory=list)
    alive: bool = True
    reader: asyncio.Task | None = None


class StdioPool:
    """Modern MCP peers over stdio, one process each, called concurrently.

    Each run of a peer's process is discovered from scratch: server/discover stamped with
    modern_versions[0], then everything else at the highest version both sides support.
    """

    def __init__(
        self,
        spawners: Mapping[str, Spawner],
        *,
        retry_safe: Mapping[str, Collection[str]] | None = None,
        modern_versions: Sequence[str] = (PROTOCOL_VERSION,),
        capabilities: dict | None = None,
    ) -> None:
        self.spawners = dict(spawners)
        # the operator's list of tools that are safe to send twice, per peer
        self.retry_safe = {peer: frozenset(tools) for peer, tools in (retry_safe or {}).items()}
        self.modern_versions = tuple(modern_versions)
        self.capabilities = dict(capabilities or {})
        self.ids = itertools.count(1)
        self._links: dict[str, _Link] = {}
        self._locks = {peer: asyncio.Lock() for peer in self.spawners}

    async def start(self) -> None:
        """Spawn every peer, discover it and list its tools."""
        await asyncio.gather(*(self._link(peer) for peer in sorted(self.spawners)))

    async def call(self, peer: str, tool: str, arguments: dict) -> dict:
        """Send tools/call to one peer and return the result.

        Calls may be in flight on many peers at once, several per peer, and a peer may answer them
        in any order; a peer that is slow to answer holds up only its own calls. A call whose
        peer is down restarts it first: spawn, server/discover, tools/list, all from scratch.

        If the process dies with the call in flight, the call fails with TransportLost, unless
        the operator listed the tool in retry_safe for that peer: then it is sent once more, with
        a new id, on the restarted peer. Tool annotations such as readOnlyHint come from the
        server and never make a call safe to retry.
        """
        params = {"name": tool, "arguments": arguments}
        link = await self._link(peer)
        try:
            return await self._ask(peer, link, "tools/call", params)
        except TransportLost:
            if tool not in self.retry_safe.get(peer, ()):
                raise
        link = await self._link(peer)
        return await self._ask(peer, link, "tools/call", params)

    async def _link(self, peer: str) -> _Link:
        """The live run of a peer's process, started and discovered if there is none."""
        async with self._locks[peer]:
            link = self._links.get(peer)
            if link is not None and link.alive:
                return link
            link = _Link(self.spawners[peer]())
            link.reader = asyncio.ensure_future(self._read(peer, link))
            self._links[peer] = link
            probe_version = self.modern_versions[0]
            discovered = await self._ask(peer, link, "server/discover", {}, probe_version)
            link.selection = modern_selection(discovered, self.modern_versions)
            listed = await self._ask(peer, link, "tools/list", {})
            link.tools = sorted(listed.get("tools", []), key=lambda item: item["name"])
            return link

    async def _ask(
        self, peer: str, link: _Link, method: str, params: dict, version: str | None = None
    ) -> dict:
        if not link.alive:
            raise TransportLost(f"{peer}: the process is gone")
        version = version or link.selection.protocol_version
        request = modern_request(next(self.ids), method, params, version, self.capabilities)
        answer: asyncio.Future = asyncio.get_running_loop().create_future()
        link.pending.add(request, answer)
        link.process.stdin.write(json.dumps(request).encode("utf-8") + b"\n")
        await link.process.stdin.drain()
        kind, payload = decode_response(await answer)
        if kind == "error":
            raise ProtocolError(f"{peer}: {method} failed with {payload['code']} {payload['message']}")
        return payload

    async def _read(self, peer: str, link: _Link) -> None:
        """Hand every answer on the peer's stdout to the call waiting for it, until EOF."""
        try:
            while True:
                line = await link.process.stdout.readline()
                if not line:
                    break
                try:
                    message = json.loads(line)
                    _, answer = link.pending.resolve(message)
                except (ValueError, ProtocolError):
                    continue  # not an answer to anything in flight
                if not answer.done():
                    answer.set_result(message)
        finally:
            link.alive = False
            for request, answer in link.pending.drain():
                if not answer.done():
                    answer.set_exception(TransportLost(f"{peer}: {request['method']} was in flight"))
