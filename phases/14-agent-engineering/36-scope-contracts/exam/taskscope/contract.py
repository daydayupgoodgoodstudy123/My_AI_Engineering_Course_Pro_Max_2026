"""Scope contracts, run summaries, and the least-privilege merge of two contracts."""
from __future__ import annotations

from dataclasses import dataclass, field

ALTITUDES = ("project", "feature", "task", "subtask")


@dataclass
class ScopeContract:
    """One scope_contract.json: where a task's work begins and where it ends.

    allowed_files and forbidden_files are globs. allowed_within holds further
    allow-lists a path must also match, one per contract this one was merged with
    (see merge_contracts); a contract read from disk has none. network_egress is
    None for no enforcement, [] for deny-all, or an allowlist of host names.
    violation_budget is how many off-scope files a run may write before the gate
    refuses it. altitude is "project", "feature", "task" or "subtask", and parent is
    the task_id of the contract one altitude up (None for the project contract).
    """

    task_id: str
    goal: str
    allowed_files: list[str]
    forbidden_files: list[str]
    acceptance_criteria: list[str]
    rollback_plan: str
    approvals_required: list[str] = field(default_factory=list)
    time_budget_minutes: int | None = None
    network_egress: list[str] | None = None
    violation_budget: int = 0
    docs_paths_soft: list[str] = field(default_factory=lambda: ["docs/**", "README.md", "**/*.md"])
    allowed_within: list[list[str]] = field(default_factory=list)
    altitude: str = "task"
    parent: str | None = None


@dataclass
class RunSummary:
    """What one agent run did.

    touched_files lists the files the run wrote, in the order it first touched them;
    a file shows up again when a later step wrote it again.
    """

    touched_files: list[str]
    commands_run: list[str]
    elapsed_minutes: float = 0.0
    network_hosts: list[str] = field(default_factory=list)


def merge_contracts(parent: ScopeContract, child: ScopeContract) -> ScopeContract:
    """Least-privilege merge of a contract and a contract that narrows it.

    allowed_files: both contracts must permit a path. Globs do not intersect as
        strings ("lib/**/*.py" and "lib/core/*.py" share no string but share paths),
        so the merged contract keeps both lists: allowed_files is the child's list,
        and allowed_within is the parent's allowed_within, then the parent's
        allowed_files, then the child's allowed_within.
    forbidden_files: the union, sorted (either contract can prohibit a path).
    acceptance_criteria, approvals_required: accumulate in order, without repeats.
    time_budget_minutes: the smaller one; None means no budget.
    network_egress: None defers to the other side, two lists intersect (sorted), and
        an empty list (deny-all) stays deny-all.
    violation_budget: the smaller one.
    docs_paths_soft: the union, sorted.
    task_id, altitude, parent: the child's. goal and rollback_plan: the child's,
        or the parent's when the child leaves them empty.
    """
    return ScopeContract(
        task_id=child.task_id,
        goal=child.goal or parent.goal,
        allowed_files=sorted(set(parent.allowed_files) & set(child.allowed_files)),
        forbidden_files=sorted(set(parent.forbidden_files) | set(child.forbidden_files)),
        acceptance_criteria=list(dict.fromkeys(parent.acceptance_criteria + child.acceptance_criteria)),
        rollback_plan=child.rollback_plan or parent.rollback_plan,
        approvals_required=list(dict.fromkeys(parent.approvals_required + child.approvals_required)),
        time_budget_minutes=_min_optional(parent.time_budget_minutes, child.time_budget_minutes),
        network_egress=_merge_egress(parent.network_egress, child.network_egress),
        violation_budget=min(parent.violation_budget, child.violation_budget),
        docs_paths_soft=sorted(set(parent.docs_paths_soft) | set(child.docs_paths_soft)),
        altitude=child.altitude,
        parent=child.parent,
    )


def _merge_egress(a: list[str] | None, b: list[str] | None) -> list[str] | None:
    if a is None and b is None:
        return None
    if a is None:
        return list(b)
    if b is None:
        return list(a)
    return sorted(set(a) & set(b))


def _min_optional(a: int | None, b: int | None) -> int | None:
    if a is None:
        return b
    if b is None:
        return a
    return min(a, b)
