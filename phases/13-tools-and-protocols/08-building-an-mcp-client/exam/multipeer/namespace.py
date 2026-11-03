"""Merge every peer's tools into one namespace of canonical tool names."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

POLICIES = ("prefix-on-collision", "reject-on-collision")
SEPARATOR = "/"


@dataclass(frozen=True)
class Route:
    """Where a canonical tool name goes: the peer that owns the tool and the name that peer declared."""

    peer: str
    local_name: str


class NamespaceError(ValueError):
    """The peers' tools cannot be merged under the chosen policy."""


def merge_namespace(
    catalogs: Mapping[str, Sequence[dict]],
    policy: str = "prefix-on-collision",
) -> dict[str, Route]:
    """Merge every peer's tool list into one namespace, whatever order the peers connected in.

    catalogs maps a peer name to the tools that peer listed (dicts with a "name"). Peers and their
    tools are taken in sorted order. A tool keeps its bare local name unless an earlier peer took
    that name first. When one did, prefix-on-collision exposes the tool as <peer>/<local>, and
    reject-on-collision raises NamespaceError naming both peers.

    A local name that already contains "/" (the peer is itself a gateway) is always exposed as
    <peer>/<local>: bare, it would read as another peer's prefixed name. So a canonical name either
    has no "/" and is the local name, or splits at its first "/" into peer and local name, and no
    two tools ever share one. A peer name may not contain "/", and a peer that lists the same name
    twice is an error under either policy. Nothing is ever silently overwritten.
    """
    raise NotImplementedError
