"""Let 2025-11-25 clients in through a separate door, so the modern core stays stateless."""
from __future__ import annotations

import traceback
from copy import deepcopy
from dataclasses import dataclass
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
MODERN_RESULT_FIELDS = ("resultType", "ttlMs", "cacheScope")


@dataclass(frozen=True)
class LegacyHandshake:
    """What initialize declared on one 2025-11-25 connection."""

    client_capabilities: dict[str, Any]
    client_info: dict[str, Any]


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
        self._handshakes: dict[str, LegacyHandshake] = {}

    def handle(self, connection: str, message: dict[str, Any], principal: str | None = None) -> dict[str, Any] | None:
        """Answer one message that arrived on connection."""
        if _is_modern(message):
            return self.core.handle(message, principal)
        if message.get("method") == "initialize":
            return self._initialize(connection, message)
        if connection in self._handshakes:
            return self._legacy_request(message, principal)
        return self.core.handle(message, principal)

    def close(self, connection: str) -> None:
        """The transport behind connection has ended: forget its handshake, if it made one."""
        self._handshakes.pop(connection, None)

    def _initialize(self, connection: str, message: dict[str, Any]) -> dict[str, Any] | None:
        if "id" not in message:
            return None
        request_id = message["id"]
        if not valid_request_id(request_id):
            return rpc_error(None, -32600, "id must be a string or a safe integer")
        params = message.get("params")
        if not (
            isinstance(params, dict)
            and isinstance(params.get("protocolVersion"), str)
            and isinstance(params.get("capabilities"), dict)
            and _valid_client_info(params.get("clientInfo"))
        ):
            return rpc_error(request_id, -32602, "initialize needs protocolVersion, capabilities and clientInfo")
        self._handshakes[connection] = LegacyHandshake(
            deepcopy(params["capabilities"]), deepcopy(params["clientInfo"])
        )
        result = {
            "protocolVersion": LEGACY_VERSION,
            "capabilities": deepcopy(SERVER_CAPABILITIES),
            "serverInfo": dict(SERVER_INFO),
            "instructions": INSTRUCTIONS,
        }
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def _legacy_request(self, message: dict[str, Any], principal: str | None) -> dict[str, Any] | None:
        if "id" not in message:
            return None  # notifications/initialized and friends
        request_id = message["id"]
        error_id = request_id if valid_request_id(request_id) else None
        method = message.get("method")
        try:
            if message.get("jsonrpc") != "2.0" or error_id is None or not isinstance(method, str):
                raise RpcProblem(-32600, "Invalid Request")
            if method not in LEGACY_METHODS:
                raise RpcProblem(-32601, f"Method not found: {method}")
            params = message.get("params", {})
            if not isinstance(params, dict):
                raise RpcProblem(-32602, "params must be an object")
            result = self.core.run(method, params, principal)
        except RpcProblem as exc:
            return rpc_error(error_id, exc.code, str(exc), exc.data)
        except Exception:
            self.core.log(f"internal error in legacy {method!r}:\n{traceback.format_exc()}")
            return rpc_error(error_id, -32603, "Internal error")
        return {"jsonrpc": "2.0", "id": request_id, "result": _legacy_shape(result)}


def _is_modern(message: dict[str, Any]) -> bool:
    params = message.get("params")
    meta = params.get("_meta") if isinstance(params, dict) else None
    return isinstance(meta, dict) and any(key in meta for key in MODERN_META_KEYS)


def _valid_client_info(info: Any) -> bool:
    return isinstance(info, dict) and isinstance(info.get("name"), str) and isinstance(info.get("version"), str)


def _legacy_shape(result: dict[str, Any]) -> dict[str, Any]:
    plain = {key: value for key, value in result.items() if key not in MODERN_RESULT_FIELDS and key != "_meta"}
    meta = {key: value for key, value in result.get("_meta", {}).items() if key != SERVER_INFO_KEY}
    if meta:
        plain["_meta"] = meta
    return plain
