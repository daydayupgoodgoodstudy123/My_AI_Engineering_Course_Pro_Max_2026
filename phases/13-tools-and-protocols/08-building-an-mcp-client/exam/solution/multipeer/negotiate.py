"""The stdio compatibility probe: choose the modern or the legacy era for one pinned peer."""
from __future__ import annotations

from collections.abc import Iterator, Sequence

from .client import Transport
from .peerconf import PeerConfig
from .protocol import (
    CLIENT_INFO,
    PROTOCOL_VERSION,
    RECOGNIZED_MODERN_ERRORS,
    ProtocolError,
    Selection,
    decode_response,
    legacy_request,
    modern_request,
    modern_selection,
    mutual_version,
    notification,
    same_id,
)


def negotiate(
    config: PeerConfig,
    transport: Transport,
    ids: Iterator[int],
    *,
    modern_versions: Sequence[str] = (PROTOCOL_VERSION,),
    capabilities: dict | None = None,
    discovery_timeout_ms: int = 1000,
) -> Selection:
    """Choose the protocol era for one stdio peer, and fail closed.

    Every request takes a new id from ids. The first request is server/discover, stamped with
    modern_versions[0] and sent under discovery_timeout_ms. Then:

    - A DiscoverResult makes the peer modern, at the highest version both sides support.
    - A recognized modern error (-32020, -32021, -32022) makes the peer modern too, even when it
      is allowlisted for legacy. For -32022, retry server/discover once, with a new id, at the
      highest version in error.data.supported that we also support. -32020 and -32021 fail:
      the request has to be corrected first.
    - Anything else is ambiguous: a timeout (TimeoutError), a closed connection (ConnectionError),
      an empty answer (None), or any other error code, -32601 included. Without
      config.allow_legacy the peer fails here. With it, send one initialize asking for
      config.legacy_revisions[0], under config.probe_timeout_ms. Accept the legacy era only if the
      answer is JSON-RPC 2.0 with the same id, has a result and no error, names a protocolVersion
      in config.legacy_revisions, has an object capabilities, and has a serverInfo whose name
      and version are non-empty strings. Only then send notifications/initialized.

    Failure raises ProtocolError, and nothing more is sent to the peer. protocol.py has the
    wire helpers.
    """
    capabilities = dict(capabilities or {})
    probe = modern_request(next(ids), "server/discover", {}, modern_versions[0], capabilities)
    outcome = _ask(transport, probe, discovery_timeout_ms)
    if outcome is None:
        return _legacy_probe(config, transport, ids, capabilities, "server/discover got no answer")
    kind, payload = outcome
    if kind == "result":
        return modern_selection(payload, modern_versions)
    code = payload["code"]
    if code not in RECOGNIZED_MODERN_ERRORS:
        return _legacy_probe(config, transport, ids, capabilities, f"server/discover failed with {code}")
    if code != -32022:
        raise ProtocolError(f"{config.name}: modern error {code}; correct the request, never downgrade")
    data = payload.get("data")
    offered = data.get("supported") if isinstance(data, dict) else None
    version = mutual_version(offered, modern_versions) if isinstance(offered, list) else None
    if version is None:
        raise ProtocolError(f"{config.name}: no mutually supported modern version")
    retry = modern_request(next(ids), "server/discover", {}, version, capabilities)
    outcome = _ask(transport, retry, discovery_timeout_ms)
    if outcome is None or outcome[0] != "result":
        raise ProtocolError(f"{config.name}: modern discovery at {version} failed")
    return modern_selection(outcome[1], modern_versions)


def _ask(transport: Transport, request: dict, timeout_ms: int) -> tuple[str, dict] | None:
    """Send one request. None means silence: a timeout, a closed connection or an empty answer."""
    try:
        response = transport(request, timeout_ms)
    except (TimeoutError, ConnectionError):
        return None
    if response is None:
        return None
    if not isinstance(response, dict) or not same_id(response.get("id"), request["id"]):
        raise ProtocolError(f"the answer to {request['method']} carries another id")
    return decode_response(response)


def _legacy_probe(
    config: PeerConfig,
    transport: Transport,
    ids: Iterator[int],
    capabilities: dict,
    trigger: str,
) -> Selection:
    if not config.allow_legacy or not config.legacy_revisions:
        raise ProtocolError(f"{config.name}: {trigger}; legacy compatibility is not allowlisted")
    initialize = legacy_request(
        next(ids),
        "initialize",
        {
            "protocolVersion": config.legacy_revisions[0],
            "capabilities": capabilities,
            "clientInfo": dict(CLIENT_INFO),
        },
    )
    outcome = _ask(transport, initialize, config.probe_timeout_ms)
    if outcome is None:
        raise ProtocolError(f"{config.name}: the bounded legacy probe got no answer")
    kind, result = outcome
    if kind != "result":
        raise ProtocolError(f"{config.name}: initialize failed")
    version = result.get("protocolVersion")
    server_info = result.get("serverInfo")
    if not isinstance(version, str) or version not in config.legacy_revisions:
        raise ProtocolError(f"{config.name}: unsupported legacy revision {version!r}")
    if not isinstance(result.get("capabilities"), dict):
        raise ProtocolError(f"{config.name}: initialize capabilities must be an object")
    if not (
        isinstance(server_info, dict)
        and all(isinstance(server_info.get(key), str) and server_info[key] for key in ("name", "version"))
    ):
        raise ProtocolError(f"{config.name}: initialize serverInfo needs a name and a version")
    transport(notification("notifications/initialized"), None)
    return Selection("legacy", version, result["capabilities"], server_info)
