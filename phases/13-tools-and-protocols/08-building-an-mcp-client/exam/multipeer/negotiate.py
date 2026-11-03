"""The stdio compatibility probe: choose the modern or the legacy era for one pinned peer."""
from __future__ import annotations

from collections.abc import Iterator, Sequence

from .client import Transport
from .peerconf import PeerConfig
from .protocol import PROTOCOL_VERSION, Selection


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
    raise NotImplementedError
