"""The verdict: findings from every source, --strict, and signed human overrides."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace

from .checks import COVERAGE_FLOOR_DEFAULT, acceptance_findings, coverage_findings, rule_findings, scope_findings
from .model import Artifacts, Finding, Verdict
from .signing import verify_signature

NOT_OVERRIDABLE = frozenset({"feedback.null_exit"})


def apply_overrides(
    findings: list[Finding],
    entries: Iterable[dict],
    *,
    task_id: str,
    head_commit: str,
    secret: bytes,
) -> list[Finding]:
    """Mark the block findings a human signed off on as overridden.

    An entry counts when its signature verifies with secret, its task_id is this task's, and its
    head_commit is the commit the findings were made at. An override recorded at another HEAD is
    stale: the code changed after the human looked. A counting entry overrides the block findings
    whose code is its finding_code, and no others. Only block findings can be overridden, and never
    feedback.null_exit: with no exit code there is nothing to sign off on.

    An overridden finding keeps its code and detail, takes severity "overridden", and carries the
    entry's user_id and reason as overridden_by and override_reason; when several entries count for
    one code, the last one does. Returns new findings, in the same order.
    """
    signed_off: dict[str, dict] = {}
    for entry in entries:
        if entry.get("task_id") == task_id and verify_signature(entry, secret):
            signed_off[entry.get("finding_code")] = entry
    out: list[Finding] = []
    for finding in findings:
        entry = signed_off.get(finding.code)
        if entry is not None and finding.severity == "block" and finding.code not in NOT_OVERRIDABLE:
            out.append(
                replace(finding, severity="overridden", overridden_by=entry["user_id"], override_reason=entry["reason"])
            )
        else:
            out.append(finding)
    return out


def verify(
    art: Artifacts,
    overrides: Iterable[dict] = (),
    *,
    secret: bytes,
    strict: bool = False,
    coverage_floor: float = COVERAGE_FLOOR_DEFAULT,
) -> Verdict:
    """The gate: one verdict for one task close-out, the same every time for the same artifacts.

    Findings come source by source, each source in its own order:

    1. acceptance: gate.no_acceptance (block) when the contract lists no acceptance command, because
       a gate that proves nothing is theater; otherwise gate.missing_artifact when the feedback log
       is missing; otherwise acceptance_findings(art).
    2. scope: gate.missing_artifact when the scope report is missing, else scope_findings.
    3. rules: gate.missing_artifact when the rule report is missing, else rule_findings.
    4. coverage: coverage_findings(art.coverage_report, coverage_floor). No coverage report is a warn.

    A missing artifact is None, and its finding is a block whose detail is "missing artifact: " and
    the file name: feedback_record.jsonl, scope_report.json or rule_report.json. An empty artifact
    exists; it simply has nothing in it.

    With strict (--strict, opt-in per branch) every warn becomes a block, and info stays info. The
    overrides are applied after that, at art.head_commit, so a human can sign off on a block that
    strict made. passed is True when no block is left. The verdict's coverage is art.coverage_report.

    coverage_floor is a fraction, 0.8 meaning 80%; a floor outside (0, 1] raises ValueError.
    """
    raise NotImplementedError
