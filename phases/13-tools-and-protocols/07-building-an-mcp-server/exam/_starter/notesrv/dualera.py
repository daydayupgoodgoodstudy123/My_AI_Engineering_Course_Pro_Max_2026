"""Let 2025-11-25 clients in through a separate door, so the modern core stays stateless."""
from __future__ import annotations

from typing import Any

from .protocol import (
    CAPABILITIES_KEY,
    CLIENT_INFO_KEY,
    SERVER_INFO,
    SERVER_INFO_KEY,
    VERSION_KEY,
    RpcProblem,
    rpc_error,
    valid_request_id,
)
from .server import INSTRUCTIONS, SERVER_CAPABILITIES, NotesServer

LEGACY_VERSION = "2025-11-25"
LEGACY_METHODS = ("prompts/get", "prompts/list", "resources/list", "resources/read", "tools/call", "tools/list")
MODERN_META_KEYS = (VERSION_KEY, CAPABILITIES_KEY, CLIENT_INFO_KEY)


class DualEraServer:
    """One process, two protocol eras, chosen message by message.

    - A message whose params._meta holds any modern request key (protocol version, client
      capabilities, client info) is modern. It goes to the stateless core, NotesServer.handle,
      and is judged on its own metadata, whatever its connection did before. Other _meta keys,
      such as a 2025-11-25 progressToken, do not make a message modern.
    - "initialize" without modern metadata is the 2025-11-25 handshake. Its params need a
      protocolVersion string, a capabilities object and a clientInfo object with string name
      and version; otherwise the answer is -32602 and nothing changes. The result is the
      2025-11-25 shape: protocolVersion, capabilities (SERVER_CAPABILITIES), serverInfo
      (SERVER_INFO) and instructions (INSTRUCTIONS). This door speaks only 2025-11-25, so that
      is the version it answers with.
    - Once a connection has shaken hands, its other messages are legacy: LEGACY_METHODS run on
      the core's handlers and come back as plain 2025-11-25 results, without resultType, ttlMs,
      cacheScope or the serverInfo stamp in _meta. Other methods get -32601.
    - Anything else goes to the core, which rejects the missing metadata.

    Handshakes belong to one connection, and close() forgets them.
    """

    def __init__(self, core: NotesServer) -> None:
        self.core = core

    def handle(self, connection: str, message: dict[str, Any], principal: str | None = None) -> dict[str, Any] | None:
        """Answer one message that arrived on connection."""
        raise NotImplementedError

    def close(self, connection: str) -> None:
        """The transport behind connection has ended: forget its handshake, if it made one."""
        raise NotImplementedError
