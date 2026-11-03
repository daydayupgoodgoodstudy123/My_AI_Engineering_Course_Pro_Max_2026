"""Concurrent tool calls to several stdio peers, surviving peers that crash.

A spawner starts one run of a peer's process and returns it. The pool uses only this much of it,
the same shape as asyncio's subprocess pipes:

    process.stdin.write(data: bytes)      # what the server reads on stdin
    await process.stdin.drain()
    await process.stdout.readline()       # one line the server wrote; b"" once it has exited

Every message on the wire is one JSON-RPC object on one line, ending in a newline.
"""
from __future__ import annotations

import itertools
from collections.abc import Callable, Collection, Mapping, Sequence
from typing import Any

from .protocol import PROTOCOL_VERSION

Spawner = Callable[[], Any]


class TransportLost(ConnectionError):
    """The peer's process went away while the call was in flight, and the call was not retried."""


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

    async def start(self) -> None:
        """Spawn every peer, discover it and list its tools."""
        raise NotImplementedError

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
        raise NotImplementedError
