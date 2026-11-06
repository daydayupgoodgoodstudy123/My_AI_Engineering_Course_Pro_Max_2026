"""The gate's checks, one source artifact at a time."""
from __future__ import annotations

import math

from .commands import command_text, latest_runs
from .model import SEVERITIES, Artifacts, Finding

COVERAGE_FLOOR_DEFAULT = 0.80
COVERAGE_REGRESSION_DELTA = 0.01


def acceptance_findings(art: Artifacts) -> list[Finding]:
    """What the feedback log proves about the acceptance commands, at most one finding per command, in contract order.

    Only the latest run of a command counts: a failure that a later run of the same command fixed is
    history, and a pass that a later run broke is no longer a pass.

    - acceptance.missing (block), "never ran: <command>": the command never ran.
    - feedback.null_exit (block), "no exit code: <command>": its latest run has no exit code,
      because the runner died before it captured one.
    - acceptance.failed (block), "exit <code>: <command>": its latest run exited non-zero.

    <command> is the acceptance command as the contract spells it.
    """
    runs = latest_runs(art.feedback)
    findings: list[Finding] = []
    for cmd in art.acceptance_commands:
        run = runs.get(command_text(cmd))
        if run is None:
            findings.append(Finding("acceptance.missing", "block", f"never ran: {cmd}"))
        elif run.get("exit_code") is None:
            findings.append(Finding("feedback.null_exit", "block", f"no exit code: {cmd}"))
        elif run["exit_code"] != 0:
            findings.append(Finding("acceptance.failed", "block", f"exit {run['exit_code']}: {cmd}"))
    return findings


def scope_findings(report: dict) -> list[Finding]:
    """Lesson 36's scope report as findings, in this order.

    - scope.forbidden (block): forbidden_writes.
    - scope.off_scope: off_scope_writes; a warn, or a block when the report is over_budget.
    - scope.soft_off_scope (info): soft_off_scope_writes, docs paths the contract treats softly.

    Each detail lists the paths sorted, so the same writes always read the same.
    """
    findings: list[Finding] = []
    if report.get("forbidden_writes"):
        findings.append(Finding("scope.forbidden", "block", "forbidden writes: " + _paths(report["forbidden_writes"])))
    if report.get("off_scope_writes"):
        severity = "block" if report.get("over_budget") else "warn"
        findings.append(Finding("scope.off_scope", severity, "off-scope writes: " + _paths(report["off_scope_writes"])))
    if report.get("soft_off_scope_writes"):
        findings.append(
            Finding("scope.soft_off_scope", "info", "soft off-scope writes: " + _paths(report["soft_off_scope_writes"]))
        )
    return findings


def _paths(paths: list[str]) -> str:
    return ", ".join(sorted(paths))


def rule_findings(rows: list[dict]) -> list[Finding]:
    """Lesson 33's rule report as findings: one rule.failed per failed rule, in report order.

    A failed rule keeps the severity it was written with, block, warn or info, since lesson 33 tags
    severity when a rule is written and the gate must not change it when it reads. A row whose
    severity is missing or is not one of those three, spelled exactly so, is a block: the gate fails
    closed rather than guess.
    """
    findings: list[Finding] = []
    for row in rows:
        if not row.get("passed"):
            severity = row.get("severity")
            if severity not in SEVERITIES:
                severity = "block"
            findings.append(Finding("rule.failed", severity, f"rule failed: {row.get('slug')}"))
    return findings


def coverage_findings(report: dict | None, floor: float = COVERAGE_FLOOR_DEFAULT) -> list[Finding]:
    """The coverage floor check, as a first-class check.

    - coverage.missing (warn): there is no coverage report, so the floor cannot be enforced.
    - coverage.below_floor (block): current coverage is under the floor.
    - coverage.regression (block): current is more than COVERAGE_REGRESSION_DELTA (one percentage
      point) below previous.
    - coverage.minor_regression (warn): a smaller drop.

    A drop of exactly one point is minor even though 0.85 - 0.84 is 0.010000000000000009 in floating
    point, and coverage equal to previous up to float noise is no drop at all.
    """
    if not report:
        return [Finding("coverage.missing", "warn", "no coverage_report.json; cannot enforce floor")]
    findings: list[Finding] = []
    current = float(report.get("current", 0.0))
    previous = float(report.get("previous", current))
    if current < floor:
        findings.append(Finding("coverage.below_floor", "block", f"coverage {current:.2%} below floor {floor:.0%}"))
    delta = previous - current
    if delta > COVERAGE_REGRESSION_DELTA and not math.isclose(delta, COVERAGE_REGRESSION_DELTA, rel_tol=1e-9):
        findings.append(
            Finding("coverage.regression", "block", f"coverage dropped {delta:.2%} (prev {previous:.2%} -> {current:.2%})")
        )
    elif delta > 0 and not math.isclose(delta, 0.0, abs_tol=1e-12):
        findings.append(Finding("coverage.minor_regression", "warn", f"coverage dropped {delta:.2%}"))
    return findings
