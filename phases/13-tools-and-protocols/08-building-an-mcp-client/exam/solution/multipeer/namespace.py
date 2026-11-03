"""Merge every peer's tools into one namespace of canonical tool names."""
from __future__ import annotations

from collections import Counter
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
    if policy not in POLICIES:
        raise ValueError(f"policy must be one of {POLICIES}, got {policy!r}")
    routes: dict[str, Route] = {}
    collisions: list[str] = []
    for peer in sorted(catalogs):
        if not peer or SEPARATOR in peer:
            raise NamespaceError(f"peer name {peer!r} must be non-empty and free of {SEPARATOR!r}")
        names = [tool.get("name") for tool in catalogs[peer]]
        if not all(isinstance(name, str) and name for name in names):
            raise NamespaceError(f"{peer} lists a tool without a name")
        twice = sorted(name for name, count in Counter(names).items() if count > 1)
        if twice:
            raise NamespaceError(f"{peer} lists {', '.join(twice)} more than once")
        for local in sorted(names):
            if SEPARATOR not in local:
                owner = routes.get(local)
                if owner is None:
                    routes[local] = Route(peer, local)
                    continue
                if policy == "reject-on-collision":
                    collisions.append(f"{local!r} is offered by {owner.peer} and {peer}")
                    continue
            canonical = f"{peer}{SEPARATOR}{local}"
            if canonical in routes:  # cannot happen: peer names have no "/"
                raise NamespaceError(f"canonical name {canonical!r} is taken")
            routes[canonical] = Route(peer, local)
    if collisions:
        raise NamespaceError("tool name collision: " + "; ".join(collisions))
    return dict(sorted(routes.items()))
