"""Pinned peer configuration, kept in an INI file that an operator reads and edits.

    # one section per pinned peer, named after the peer
    [archive]
    argv = archive-mcp --listen 127.0.0.1:%PORT% --banner "it's old"
    allow_legacy = true
    legacy_revisions = 2025-11-25 2024-11-05
    probe_timeout_ms = 275

    [files]
    endpoint = https://files.internal.example/mcp

A peer has exactly one of argv (a stdio command, quoted the way a POSIX shell quotes it) or
endpoint. allow_legacy defaults to false, legacy_revisions to none (space-separated, preferred
first) and probe_timeout_ms to 1000. Every value is taken literally: % is just a character.

Legacy compatibility is operator intent bound to one pinned peer, so nothing may grant it more
widely: no [DEFAULT] section (it applies to every peer), and no wildcard (*) in a peer name or an
endpoint. The era a peer negotiated is not configuration and is never written here.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from os import PathLike

DEFAULT_PROBE_TIMEOUT_MS = 1000


@dataclass(frozen=True)
class PeerConfig:
    """One pinned peer: a stdio command (argv) or an HTTP endpoint, and its legacy permission."""

    name: str
    argv: tuple[str, ...] = ()
    endpoint: str | None = None
    allow_legacy: bool = False
    legacy_revisions: tuple[str, ...] = ()
    probe_timeout_ms: int = DEFAULT_PROBE_TIMEOUT_MS


def save_peers(path: str | PathLike, peers: Sequence[PeerConfig]) -> None:
    """Write pinned peers to an INI file that load_peers reads back exactly, in the same order."""
    raise NotImplementedError


def load_peers(path: str | PathLike) -> list[PeerConfig]:
    """Read pinned peers from an INI file, in file order. Anything invalid raises ValueError."""
    raise NotImplementedError
