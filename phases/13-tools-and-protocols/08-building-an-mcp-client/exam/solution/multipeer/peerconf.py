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

import configparser
import shlex
from collections.abc import Sequence
from dataclasses import dataclass
from os import PathLike

KEYS = ("argv", "endpoint", "allow_legacy", "legacy_revisions", "probe_timeout_ms")
WILDCARD = "*"
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


def check_peer(config: PeerConfig) -> None:
    """Raise ValueError unless config pins exactly one command or endpoint."""
    if not config.name or WILDCARD in config.name:
        raise ValueError(f"peer name {config.name!r} does not pin one peer")
    if bool(config.argv) == (config.endpoint is not None):
        raise ValueError(f"peer {config.name!r} needs exactly one of argv or endpoint")
    if config.endpoint is not None and WILDCARD in config.endpoint:
        raise ValueError(f"peer {config.name!r}: a wildcard endpoint does not pin one peer")
    if config.allow_legacy and not config.legacy_revisions:
        raise ValueError(f"peer {config.name!r}: allow_legacy needs at least one legacy revision")
    if type(config.probe_timeout_ms) is not int or config.probe_timeout_ms <= 0:
        raise ValueError(f"peer {config.name!r}: probe_timeout_ms must be a positive integer")


def save_peers(path: str | PathLike, peers: Sequence[PeerConfig]) -> None:
    """Write pinned peers to an INI file that load_peers reads back exactly, in the same order."""
    parser = configparser.ConfigParser(interpolation=None)
    for config in peers:
        check_peer(config)
        if parser.has_section(config.name):
            raise ValueError(f"peer {config.name!r} is listed twice")
        parser.add_section(config.name)
        section = parser[config.name]
        if config.argv:
            section["argv"] = shlex.join(config.argv)
        if config.endpoint is not None:
            section["endpoint"] = config.endpoint
        section["allow_legacy"] = "true" if config.allow_legacy else "false"
        if config.legacy_revisions:
            section["legacy_revisions"] = " ".join(config.legacy_revisions)
        section["probe_timeout_ms"] = str(config.probe_timeout_ms)
    with open(path, "w", encoding="utf-8") as fh:
        parser.write(fh)


def load_peers(path: str | PathLike) -> list[PeerConfig]:
    """Read pinned peers from an INI file, in file order. Anything invalid raises ValueError."""
    parser = configparser.ConfigParser(interpolation=None)
    with open(path, encoding="utf-8") as fh:  # read() would skip a missing file silently
        try:
            parser.read_file(fh)
        except configparser.Error as exc:  # duplicate peers or keys, keys outside a section
            raise ValueError(f"{path}: {exc}") from exc
    if parser.defaults():
        raise ValueError("a [DEFAULT] section would apply to every peer")
    return [_peer(name, parser[name]) for name in parser.sections()]


def _peer(name: str, section: configparser.SectionProxy) -> PeerConfig:
    unknown = sorted(set(section) - set(KEYS))
    if unknown:
        raise ValueError(f"peer {name!r}: unknown keys {unknown}")
    try:
        config = PeerConfig(
            name=name,
            argv=tuple(shlex.split(section["argv"])) if "argv" in section else (),
            endpoint=section.get("endpoint"),
            allow_legacy=section.getboolean("allow_legacy", fallback=False),
            legacy_revisions=tuple(section.get("legacy_revisions", "").split()),
            probe_timeout_ms=section.getint("probe_timeout_ms", fallback=DEFAULT_PROBE_TIMEOUT_MS),
        )
    except ValueError as exc:
        raise ValueError(f"peer {name!r}: {exc}") from exc
    check_peer(config)
    return config
