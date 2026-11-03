"""Route state: what is admitted, what new work goes to, and what is quarantined."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RouteState:
    """pins: every admitted pin by (server, version), kept when quarantined because it is evidence.
    active: the version each server sends new work to; a server with no active version is absent.
    quarantined: the (server, version) pairs that may never receive new work again.
    """

    pins: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    active: dict[str, str] = field(default_factory=dict)
    quarantined: set[tuple[str, str]] = field(default_factory=set)

    def state_of(self, server: str, version: str) -> str:
        """The rollout state of one version, one word each:

        "quarantined"  it may not receive new work;
        "active"       the route sends new work to it;
        "superseded"   another admitted version of the server is active;
        "approved"     admitted and eligible, while the server has no active version;
        "unknown"      never admitted.
        """
        key = (server, version)
        if key not in self.pins:
            return "unknown"
        if key in self.quarantined:
            return "quarantined"
        if self.active.get(server) == version:
            return "active"
        return "superseded" if server in self.active else "approved"
