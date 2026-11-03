"""Which cached App resources and mounted Views a change invalidates.

The host's state is a small dependency graph. A server serves ui:// resources; tools/list binds
each tool to one of its server's resources; the cache holds entries (copies of a resource, one
per digest and, when private, per principal); each mounted View renders a tool and was mounted
from one cache entry, which may have been evicted since.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CachedEntry:
    """One App cache entry: whose resource it is, which version, and for whom."""

    server: str
    uri: str
    digest: str
    principal: str | None = None


@dataclass(frozen=True)
class MountedView:
    """A mounted View: the tool it renders and the id of the cache entry it was mounted from."""

    server: str
    tool: str
    entry: str


@dataclass
class HostState:
    """bindings: (server, tool name) -> ui:// URI. subscriptions: acknowledged (server, URI) pairs."""

    bindings: dict[tuple[str, str], str] = field(default_factory=dict)
    entries: dict[str, CachedEntry] = field(default_factory=dict)
    views: dict[str, MountedView] = field(default_factory=dict)
    subscriptions: set[tuple[str, str]] = field(default_factory=set)


@dataclass(frozen=True)
class Plan:
    """Entry ids to drop from the cache and View ids to remount, each sorted."""

    drop: list[str]
    remount: list[str]


def plan_invalidation(state: HostState, events: list[dict]) -> Plan:
    """Work out what a batch of change events invalidates. Every event is read against state as given.

    Events, one per invalidation condition:
      {"type": "expired", "entry": entry_id}                  that entry's ttlMs ran out
      {"type": "binding", "server": s, "tool": t, "uri": u}   tools/list now binds tool t to u
      {"type": "server", "server": s}                         s's version or admitted descriptor pin changed
      {"type": "updated", "server": s, "uri": u}              a resource-change notification names u

    An expired entry is dropped on its own. The other events invalidate resources, identified
    by (server, uri): a binding change invalidates the tool's old and new resource and remounts
    the tool's own Views; a server change invalidates every resource of that server, those it
    has cache entries for and those its tools are bound to; a change notification invalidates
    its resource only when the host holds an acknowledged subscription for that (server, uri).

    An invalidated resource drops every cache entry for it, whatever the digest or principal,
    and remounts every View of a tool bound to it. Every dropped entry remounts the Views
    mounted from it. Nothing else is dropped or remounted. An unknown event type is a ValueError.
    """
    raise NotImplementedError
