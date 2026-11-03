"""Glue for the route reconciler: Registry sync -> artifact verifier -> live discovery -> admission -> route table.

The ledger sits beside the route table and explains every change to it.
"""
from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any

from .admission import Decision, decide
from .evidence import REGISTRY_SOURCE, listed_version
from .ledger import AdmissionLedger
from .reconcile import reconcile
from .rollback import fold, rollback
from .state import RouteState


class AdmissionController:
    def __init__(
        self,
        ledger: AdmissionLedger,
        required_capabilities: tuple[str, ...] = ("tools",),
        registry_source: str = REGISTRY_SOURCE,
    ) -> None:
        self.ledger = ledger
        self.required_capabilities = required_capabilities
        self.registry_source = registry_source
        self.state = fold(ledger.entries) if ledger.entries else RouteState()

    def admit(
        self,
        item: dict[str, Any],
        requested: str,
        verified_namespace: str,
        evidence: dict[str, Any],
        live: Any,
    ) -> Decision:
        """Decide, record the decision, and send new work to the version when it is admitted."""
        decision = decide(
            item, requested, verified_namespace, evidence, live, self.required_capabilities, self.registry_source
        )
        listing = listed_version(item, verified_namespace)
        if decision.allowed:
            self.ledger.append("admission", listing.name, requested, "approved", [], {"pin": decision.pin})
            self.state.pins[(listing.name, requested)] = decision.pin
            self.state.active[listing.name] = requested
        else:
            evidence_seen = {
                "recordDigest": listing.record_digest,
                "status": listing.status,
                "verifiedNamespace": verified_namespace,
                "claimedNamespace": listing.namespace,
            }
            self.ledger.append("admission", listing.name, requested, "rejected", decision.reasons, evidence_seen)
        return decision

    def reconcile(self, observations: AsyncIterator[dict[str, Any]]) -> AsyncIterator[str]:
        """Check admitted versions as observations arrive; reconcile defines the verdict lines."""
        return reconcile(observations, self.state, self.ledger, self.required_capabilities)

    def rollback(self, server: str, target: str, reason: str, healthy: Callable[[str, str], bool]) -> Decision:
        """Restore a route from the ledger's evidence, then rebuild the route table from the ledger."""
        decision = rollback(self.ledger, server, target, reason, healthy)
        self.state = fold(self.ledger.entries)
        return decision
