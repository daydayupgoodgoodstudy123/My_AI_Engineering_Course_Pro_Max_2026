"""Portability as a capability matrix: what each package capability really gets on each host."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

STATUSES = ("supported", "adapter", "degraded", "unsupported")
UNCLAIMED = "no claim recorded"

# The lesson's capability table: every capability and the capabilities it depends on.
CAPABILITIES: dict[str, tuple[str, ...]] = {
    "catalog-entry": (),
    "body-activation": ("catalog-entry",),
    "companion-files": ("body-activation",),
    "process-tools": (),
    "script-execution": ("companion-files", "process-tools"),
    "explicit-invocation": ("catalog-entry",),
    "host-router": (),
    "implicit-invocation": ("host-router", "body-activation"),
    "host-extension": (),
    "invocation-policy": ("host-extension", "implicit-invocation"),
    "host-parser": (),
    "argument-binding": ("host-parser", "explicit-invocation"),
    "pre-approved-tools": (),
    "delegated-context": (),
    "lifecycle-hooks": (),
    "context-preservation": (),
}


@dataclass(frozen=True)
class Claim:
    """What one host does for one capability, one of STATUSES from best to worst, and the test or
    current official contract that shows it. A claim with blank evidence is no claim."""

    status: str
    evidence: str


def host_matrix(
    catalog: Mapping[str, Sequence[str]],
    required: Sequence[str],
    optional: Sequence[str],
    fallbacks: Mapping[str, str],
    hosts: Mapping[str, Mapping[str, Claim]],
) -> dict[str, dict[str, object]]:
    """Work out, for every host, what each required and optional capability really gets.

    catalog maps every capability to the capabilities it depends on, and fallbacks are the
    package's documented fallbacks. The whole catalog is checked first: a dependency cycle or a
    dependency missing from the catalog raises ValueError, and so does a required, optional or
    fallback name missing from it, a capability listed twice, or a claim whose status is not in
    STATUSES.

    A capability's effective status is the worst of its own claim and its dependencies' effective
    statuses; a capability the host has no claim for counts as unsupported, with the evidence
    UNCLAIMED. Its cause is the capability whose own claim set that status: itself when its own
    claim is at least as bad as every dependency, otherwise the cause of the first dependency, in
    declared order, with the worst status. Its evidence is the cause's evidence.

    outcome: supported and adapter stay as they are. A degraded or unsupported capability with a
    documented fallback is "degraded"; without one it is "silent-degradation" or "unsupported".

    For each host: blocking lists the required capabilities whose outcome is silent-degradation
    or unsupported, in required order (optional ones never block); installable is not blocking;
    verdict is "blocked" when anything blocks, otherwise "degraded", "adapter" or "native" after
    the worst required outcome. capabilities maps each required, then optional, capability to
    {"required", "outcome", "fallback" (the fallback in use, else None), "cause", "evidence"}.
    """
    _check_catalog(catalog)
    declared = [*required, *optional]
    for name in [*declared, *fallbacks]:
        if name not in catalog:
            raise ValueError(f"unknown capability {name!r}")
    if len(set(declared)) != len(declared):
        raise ValueError("each capability is required or optional, once")
    rank = {status: index for index, status in enumerate(STATUSES)}
    matrix: dict[str, dict[str, object]] = {}
    for host, claims in hosts.items():
        for name, claim in claims.items():
            if claim.status not in rank:
                raise ValueError(f"{host}: {name} has unknown status {claim.status!r}")
        memo: dict[str, tuple[int, str]] = {}

        def own(name: str) -> tuple[int, str]:
            claim = claims.get(name)
            if claim is None or not claim.evidence.strip():
                return rank["unsupported"], UNCLAIMED
            return rank[claim.status], claim.evidence

        def resolve(name: str) -> tuple[int, str]:
            if name not in memo:
                worst, cause = own(name)[0], name
                for dependency in catalog[name]:
                    level, source = resolve(dependency)
                    if level > worst:
                        worst, cause = level, source
                memo[name] = (worst, cause)
            return memo[name]

        rows: dict[str, dict[str, object]] = {}
        for name in declared:
            level, cause = resolve(name)
            status = STATUSES[level]
            fallback = None
            if status in ("supported", "adapter"):
                outcome = status
            elif fallbacks.get(name):
                outcome, fallback = "degraded", fallbacks[name]
            elif status == "degraded":
                outcome = "silent-degradation"
            else:
                outcome = "unsupported"
            rows[name] = {
                "required": name in required,
                "outcome": outcome,
                "fallback": fallback,
                "cause": cause,
                "evidence": own(cause)[1],
            }
        blocking = [name for name in required if rows[name]["outcome"] in ("silent-degradation", "unsupported")]
        outcomes = {rows[name]["outcome"] for name in required}
        if blocking:
            verdict = "blocked"
        elif "degraded" in outcomes:
            verdict = "degraded"
        elif "adapter" in outcomes:
            verdict = "adapter"
        else:
            verdict = "native"
        matrix[host] = {"verdict": verdict, "installable": not blocking, "blocking": blocking, "capabilities": rows}
    return matrix


def _check_catalog(catalog: Mapping[str, Sequence[str]]) -> None:
    done: set[str] = set()
    path: list[str] = []

    def visit(name: str) -> None:
        if name in done:
            return
        if name in path:
            raise ValueError("capability dependency cycle: " + " -> ".join([*path[path.index(name):], name]))
        path.append(name)
        for dependency in catalog[name]:
            if dependency not in catalog:
                raise ValueError(f"{name!r} depends on unknown capability {dependency!r}")
            visit(dependency)
        path.pop()
        done.add(name)

    for name in catalog:
        visit(name)
