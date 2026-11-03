"""Continuous reconciliation: keep checking admitted versions after admission, layer by layer."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from .admission import live_failures
from .evidence import digest, registry_status, toolset_digest
from .ledger import AdmissionLedger
from .state import RouteState

EVENTS = {"registry": "registry-sync", "artifact": "artifact-check", "live": "live-check"}


async def reconcile(
    observations: AsyncIterator[dict[str, Any]],
    state: RouteState,
    ledger: AdmissionLedger,
    required_capabilities: tuple[str, ...] = ("tools",),
) -> AsyncIterator[str]:
    """Judge each observation of an admitted version as it arrives, and yield one NDJSON verdict line for it.

    Every observation names "server", "version" and "check":
      "registry"  plus "item", the Registry listing item the sync worker sees for that version now
      "artifact"  plus "sourceDigest", from the verifier fetching the pinned package or remote again
      "live"      plus "live", the server/discover result (with tools) from the endpoint

    A check compares its layers with the pin, in this order:
      registry-integrity  digest() of the item's record is not the pin's recordDigest: the same
                          Registry version changed, and published metadata is immutable
      registry-status     the Registry-managed status is not active: deprecated still lists and
                          deleted hides, and both stop new work
      source-integrity    sourceDigest is not the pin's: the same package coordinate or remote
                          deployment now serves something else
      runtime-drift       live_failures(live, required_capabilities) finds anything, or
                          toolset_digest(live["tools"]) is not the pin's toolsetDigest; the
                          order of the tool list alone is no change

    A failed layer quarantines the version for good: later clean observations do not lift it.
    Quarantine takes the version off its server's route only when it is the active version, and
    the pin stays in state.pins, because it is evidence. An observation of a version that has no
    pin changes nothing and reports no layers.

    Each observation goes into the ledger before its verdict is yielded: event "registry-sync",
    "artifact-check" or "live-check"; outcome "unknown" (no pin), "quarantined" (now or before)
    or "ok"; reasons the failed layers; and as evidence only what was observed:
    {"recordDigest", "status"}, {"sourceDigest"} or {"toolsetDigest"} (None when tools is not a
    list of objects). The verdict line is one JSON object and a newline:

      {"seq": <sequence of that ledger entry>, "server", "version", "check", "layers": [...],
       "verdict": <the outcome>, "active": <the server's active version afterwards, or null>}
    """
    async for observation in observations:
        server, version, check = observation["server"], observation["version"], observation["check"]
        key = (server, version)
        pin = state.pins.get(key)
        layers, evidence = _judge(check, observation, pin, required_capabilities)
        if pin is None:
            outcome = "unknown"
        else:
            if layers:
                state.quarantined.add(key)
                if state.active.get(server) == version:
                    del state.active[server]
            outcome = "quarantined" if key in state.quarantined else "ok"
        entry = ledger.append(EVENTS[check], server, version, outcome, layers, evidence)
        verdict = {
            "seq": entry["sequence"],
            "server": server,
            "version": version,
            "check": check,
            "layers": layers,
            "verdict": outcome,
            "active": state.active.get(server),
        }
        yield json.dumps(verdict) + "\n"


def _judge(
    check: str,
    observation: dict[str, Any],
    pin: dict[str, Any] | None,
    required_capabilities: tuple[str, ...],
) -> tuple[list[str], dict[str, Any]]:
    layers: list[str] = []
    if check == "registry":
        item = observation["item"]
        observed, status = digest(item["server"]), registry_status(item.get("_meta"))
        if pin is not None and observed != pin["recordDigest"]:
            layers.append("registry-integrity")
        if pin is not None and status != "active":
            layers.append("registry-status")
        return layers, {"recordDigest": observed, "status": status}
    if check == "artifact":
        observed = observation["sourceDigest"]
        if pin is not None and observed != pin["sourceDigest"]:
            layers.append("source-integrity")
        return layers, {"sourceDigest": observed}
    if check == "live":
        live = observation["live"]
        tools = live.get("tools") if isinstance(live, dict) else None
        listed = isinstance(tools, list) and all(isinstance(tool, dict) for tool in tools)
        observed = toolset_digest(tools) if listed else None
        if pin is not None and (live_failures(live, required_capabilities) or observed != pin["toolsetDigest"]):
            layers.append("runtime-drift")
        return layers, {"toolsetDigest": observed}
    raise ValueError(f"unknown check {check!r}")
