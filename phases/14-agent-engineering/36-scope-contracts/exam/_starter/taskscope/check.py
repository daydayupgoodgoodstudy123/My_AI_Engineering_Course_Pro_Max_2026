"""Compare a run against its scope contract and report tagged findings."""
from __future__ import annotations

from dataclasses import dataclass

from .contract import RunSummary, ScopeContract
from .patterns import PatternSet


@dataclass
class Finding:
    code: str
    severity: str  # "block", "warn" or "info"
    detail: str


@dataclass
class ScopeReport:
    task_id: str
    in_scope_writes: list[str]
    off_scope_writes: list[str]
    forbidden_writes: list[str]
    soft_off_scope_writes: list[str]
    missing_acceptance: list[str]
    findings: list[Finding]
    over_budget: bool

    def passed(self) -> bool:
        return not self.over_budget and not any(f.severity == "block" for f in self.findings)


class Classifier:
    """Sorts one contract's touched paths into "forbidden", "in_scope", "soft" or "off_scope".

    Forbidden wins over allowed. A path is in scope when it matches allowed_files and
    every list in allowed_within. Outside the contract, a docs path (docs_paths_soft)
    is soft and anything else is off scope. Paths are normalized repository paths.
    """

    def __init__(self, contract: ScopeContract) -> None:
        self.forbidden = PatternSet(contract.forbidden_files)
        self.allowed = [PatternSet(contract.allowed_files), *map(PatternSet, contract.allowed_within)]
        self.soft = PatternSet(contract.docs_paths_soft)

    def classify(self, path: str) -> str:
        if self.forbidden.matches(path):
            return "forbidden"
        if all(allowed.matches(path) for allowed in self.allowed):
            return "in_scope"
        if self.soft.matches(path):
            return "soft"
        return "off_scope"


def scope_check(contract: ScopeContract, run: RunSummary) -> ScopeReport:
    """Check one run against its (merged) contract.

    Every touched file is classified once, in the order it was first touched:
    forbidden (block), in scope, soft (info) or off scope (warn). Acceptance criteria
    the run did not run block, and so does running longer than time_budget_minutes.

    violation_budget counts files: the run is over budget when more distinct files are
    off scope than the budget allows. Soft and forbidden files do not count against it.

    network_egress: None means no enforcement, [] allows no host, and a list allows
    the hosts it names. Hosts compare case-insensitively and without a port:
    "API.anthropic.com:443" is "api.anthropic.com", and an IPv6 address, written in
    brackets as in a URL, keeps them ("[2001:db8::1]:443" is "[2001:db8::1]").
    """
    classifier = Classifier(contract)
    buckets: dict[str, list[str]] = {"in_scope": [], "off_scope": [], "forbidden": [], "soft": []}
    for path in dict.fromkeys(run.touched_files):
        buckets[classifier.classify(path)].append(path)
    missing = [c for c in contract.acceptance_criteria if c not in run.commands_run]

    forbidden, off_scope, soft = buckets["forbidden"], buckets["off_scope"], buckets["soft"]
    findings: list[Finding] = []
    if forbidden:
        findings.append(Finding("scope.forbidden", "block", f"forbidden writes: {forbidden}"))
    if off_scope:
        findings.append(Finding("scope.off_scope", "warn", f"off-scope writes: {off_scope}"))
    if soft:
        findings.append(Finding("scope.soft_off_scope", "info", f"docs/markdown off-scope: {soft}"))
    if missing:
        findings.append(Finding("acceptance.missing", "block", f"acceptance not run: {missing}"))
    if contract.time_budget_minutes is not None and run.elapsed_minutes > contract.time_budget_minutes:
        findings.append(Finding("time.over_budget", "block",
                                f"elapsed {run.elapsed_minutes:.1f}m > budget {contract.time_budget_minutes}m"))
    if contract.network_egress is not None and run.network_hosts:
        bad_hosts = [h for h in run.network_hosts if h not in contract.network_egress]
        if bad_hosts:
            findings.append(Finding("network.unallowed_host", "block",
                                    f"egress to non-allowlisted hosts: {bad_hosts}"))

    warn_count = sum(1 for f in findings if f.severity == "warn")
    return ScopeReport(
        task_id=contract.task_id,
        in_scope_writes=buckets["in_scope"],
        off_scope_writes=off_scope,
        forbidden_writes=forbidden,
        soft_off_scope_writes=soft,
        missing_acceptance=missing,
        findings=findings,
        over_budget=warn_count > contract.violation_budget,
    )
