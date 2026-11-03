"""Rollback as route restoration: rebuild the state from the ledger, then decide from that evidence."""
from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

from .admission import Decision
from .ledger import AdmissionLedger
from .state import RouteState

CHECK_EVENTS = ("registry-sync", "artifact-check", "live-check")


def fold(entries: list[dict[str, Any]]) -> RouteState:
    """Rebuild the route state from ledger entries, oldest first.

      admission, approved           evidence["pin"] is admitted, and the version becomes its
                                    server's active version
      registry-sync, artifact-check,
      live-check, quarantined       the version is quarantined for good; if it is its server's
                                    active version, the server has no active version any more
      rollback, activated           evidence["to"] becomes the server's active version

    Nothing else changes the state: rejected admissions, rejected rollbacks, and checks that
    came back ok or unknown.
    """
    state = RouteState()
    for entry in entries:
        event, outcome = entry["event"], entry["outcome"]
        server, version = entry["server"], entry["version"]
        if event == "admission" and outcome == "approved":
            state.pins[(server, version)] = deepcopy(entry["evidence"]["pin"])
            state.active[server] = version
        elif event in CHECK_EVENTS and outcome == "quarantined":
            state.quarantined.add((server, version))
            if state.active.get(server) == version:
                del state.active[server]
        elif event == "rollback" and outcome == "activated":
            state.active[server] = entry["evidence"]["to"]
    return state


def rollback(
    ledger: AdmissionLedger,
    server: str,
    target: str,
    reason: str,
    healthy: Callable[[str, str], bool],
) -> Decision:
    """Send a server's new work back to an earlier admitted version, if the ledger proves it safe.

    The state comes from fold(ledger.entries), the evidence, not from anything kept in memory.
    The rules, in order; the first one that fails is the decision's only reason:

      "unknown"      the ledger holds no approved admission of target for this server
      "quarantined"  target is quarantined
      "unhealthy"    healthy(server, target) is False. This is the current health check, so it is
                     asked only when the two ledger rules pass

    Accepted or not, the decision is appended to the ledger: event "rollback", outcome
    "activated" or "rejected", reasons as above, evidence {"from": the server's active version
    before, or None, "to": target, "reason": reason}. Nothing already in the ledger changes. An
    accepted rollback returns the target's pin.
    """
    state = fold(ledger.entries)
    key = (server, target)
    if key not in state.pins:
        reasons: tuple[str, ...] = ("unknown",)
    elif key in state.quarantined:
        reasons = ("quarantined",)
    elif not healthy(server, target):
        reasons = ("unhealthy",)
    else:
        reasons = ()
    evidence = {"from": state.active.get(server), "to": target, "reason": reason}
    ledger.append("rollback", server, target, "rejected" if reasons else "activated", reasons, evidence)
    if reasons:
        return Decision(False, reasons)
    return Decision(True, (), deepcopy(state.pins[key]))
