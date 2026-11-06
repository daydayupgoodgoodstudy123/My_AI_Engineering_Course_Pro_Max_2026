"""The lesson's run comparison: a stub agent, its run record and the failure-mode report.

The agent is a rule-based stand-in for an LLM. The same task runs prompt-only and with the
seven workbench surfaces wired in, and the report maps each missing surface to the symptom
the lesson's table gives for it.
"""
from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

WORKBENCH_SURFACES = [
    "instructions",
    "state",
    "scope",
    "feedback",
    "verification",
    "review",
    "handoff",
]

# The "Failure when missing" column of the lesson's table.
SYMPTOMS = {
    "instructions": "Agent guesses what shipping means",
    "state": "Each session restarts from zero",
    "scope": "Edits leak into unrelated code",
    "feedback": "Agent declares success on a 400",
    "verification": '"Looks good" reaches main',
    "review": "Builder marks own homework",
    "handoff": "Next session re-discovers everything",
}


@dataclass
class RepoTask:
    description: str
    allowed_files: list[str]
    forbidden_files: list[str]
    acceptance: list[str]


@dataclass
class RunResult:
    label: str
    surfaces_present: list[str] = field(default_factory=list)
    files_touched: list[str] = field(default_factory=list)
    tests_run: bool = False
    declared_success: bool = False
    actually_passing: bool = False
    notes: list[str] = field(default_factory=list)

    def missing_surfaces(self) -> list[str]:
        """The surfaces this run lacks, in WORKBENCH_SURFACES order."""
        return [s for s in WORKBENCH_SURFACES if s not in self.surfaces_present]


def stub_agent(task: RepoTask, surfaces: Sequence[str], hallucinated: Sequence[str] = ()) -> RunResult:
    """Tiny deterministic stand-in for an LLM-backed coding agent.

    The run is labeled "prompt-only" with no surfaces, "workbench" with all seven and
    "partial" otherwise. The agent writes the task's allowed files. Without scope it also
    writes README.md and scripts/release.sh, then the hallucinated files; with scope those
    writes are refused. Feedback captures the test run. Verification reads the captured
    run, so without feedback the gate fails closed and the run does not pass. The agent
    declares success either way.
    """
    missing = [s for s in WORKBENCH_SURFACES if s not in surfaces]
    result = RunResult(label="prompt-only" if not surfaces else "partial" if missing else "workbench")
    result.surfaces_present = list(surfaces)

    has_scope = "scope" in surfaces
    has_state = "state" in surfaces
    has_verification = "verification" in surfaces
    has_feedback = "feedback" in surfaces

    if has_scope:
        result.files_touched = list(task.allowed_files)
        if hallucinated:
            result.notes.append("scope refused writes outside the allowed files")
    else:
        result.files_touched = [*task.allowed_files, "README.md", "scripts/release.sh", *hallucinated]
        result.notes.append("touched unrelated files because scope was missing")

    if has_feedback:
        result.tests_run = True
        result.notes.append("captured stdout/stderr/exit code from the test run")
    else:
        result.notes.append("never ran the test command, guessed at output")

    result.declared_success = True
    if has_verification and result.tests_run:
        result.actually_passing = True
        result.notes.append("verification gate proved acceptance criteria met")
    elif has_verification:
        result.notes.append("verification gate failed closed: no captured test run")
    else:
        result.notes.append("declared success without running acceptance checks")

    if not has_state:
        result.notes.append("no state file written, next session restarts from zero")

    return result


def failure_report(result: RunResult, task: RepoTask) -> dict[str, object]:
    """The failure-mode report for one run, ready for json.dumps.

    missing_surfaces lists what the run lacked, in WORKBENCH_SURFACES order, and symptoms
    maps each of them to its symptom. off_scope_writes are the files the run wrote that the
    task neither allows nor forbids; forbidden_writes are the files it wrote that the task
    forbids. Both list each file once, in the order it was first written.
    unverified_success: the run declared success without actually passing.
    """
    missing = result.missing_surfaces()
    allowed = set(task.allowed_files)
    forbidden = set(task.forbidden_files)
    off_scope: list[str] = []
    forbidden_writes: list[str] = []
    for path in dict.fromkeys(result.files_touched):
        if path in forbidden:
            forbidden_writes.append(path)
        elif path not in allowed:
            off_scope.append(path)
    return {
        "label": result.label,
        "missing_surfaces": missing,
        "symptoms": {s: SYMPTOMS[s] for s in missing},
        "off_scope_writes": off_scope,
        "forbidden_writes": forbidden_writes,
        "tests_run": result.tests_run,
        "declared_success": result.declared_success,
        "actually_passing": result.actually_passing,
        "unverified_success": result.declared_success and not result.actually_passing,
        "notes": list(result.notes),
    }


def write_report(report: dict[str, object], path: Path) -> None:
    """Write a report as indented JSON, like the lesson's failure_modes.json."""
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def compare(task: RepoTask, out: Path, hallucinated: Sequence[str] = ()) -> dict[str, dict[str, object]]:
    """Run the task prompt-only and with the full workbench, as the lesson's main() does.

    The prompt-only report is written to out. Returns both reports, keyed by label.
    """
    prompt_only = stub_agent(task, [], hallucinated)
    workbench = stub_agent(task, WORKBENCH_SURFACES, hallucinated)
    write_report(failure_report(prompt_only, task), out)
    return {run.label: failure_report(run, task) for run in (prompt_only, workbench)}
