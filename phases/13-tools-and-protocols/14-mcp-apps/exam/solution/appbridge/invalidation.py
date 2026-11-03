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
    resources: set[tuple[str, str]] = set()
    dropped: set[str] = set()
    remount: set[str] = set()
    for event in events:
        kind = event.get("type")
        if kind == "expired":
            if event["entry"] in state.entries:
                dropped.add(event["entry"])
        elif kind == "binding":
            server, tool = event["server"], event["tool"]
            old = state.bindings.get((server, tool))
            if old is not None:
                resources.add((server, old))
            resources.add((server, event["uri"]))
            remount.update(
                view_id for view_id, view in state.views.items() if (view.server, view.tool) == (server, tool)
            )
        elif kind == "server":
            server = event["server"]
            resources.update((e.server, e.uri) for e in state.entries.values() if e.server == server)
            resources.update((owner, uri) for (owner, _), uri in state.bindings.items() if owner == server)
        elif kind == "updated":
            if (event["server"], event["uri"]) in state.subscriptions:
                resources.add((event["server"], event["uri"]))
        else:
            raise ValueError(f"unknown change event {kind!r}")

    dropped.update(
        entry_id for entry_id, entry in state.entries.items() if (entry.server, entry.uri) in resources
    )
    bound = {tool for tool, uri in state.bindings.items() if (tool[0], uri) in resources}
    remount.update(
        view_id
        for view_id, view in state.views.items()
        if view.entry in dropped or (view.server, view.tool) in bound
    )
    return Plan(sorted(dropped), sorted(remount))
