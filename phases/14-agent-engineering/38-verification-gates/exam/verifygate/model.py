"""What the gate reads and what it writes."""
from __future__ import annotations

from dataclasses import asdict, dataclass

SEVERITIES = ("block", "warn", "info")  # once a human signs off on a block it becomes "overridden"


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str  # block | warn | info | overridden
    detail: str
    overridden_by: str | None = None
    override_reason: str | None = None


@dataclass(frozen=True)
class Artifacts:
    """Everything the gate reads for one task close-out.

    acceptance_commands are shell strings from the task's scope contract (lesson 36).
    feedback is the lesson 37 runner's feedback_record.jsonl, oldest record first; a record has at
    least "command" (the argv list it ran) and "exit_code" (None when the runner died first).
    scope_report is lesson 36's report: forbidden_writes, off_scope_writes, soft_off_scope_writes and
    over_budget. rule_report is lesson 33's rows, {"slug", "passed", "severity"}. coverage_report is
    {"current": 0.84, "previous": 0.85}, fractions of lines covered.

    None means the artifact does not exist. An empty list or dict exists and has nothing in it.
    """

    task_id: str
    head_commit: str
    acceptance_commands: list[str]
    feedback: list[dict] | None
    scope_report: dict | None
    rule_report: list[dict] | None
    coverage_report: dict | None = None


@dataclass(frozen=True)
class Verdict:
    task_id: str
    head_commit: str
    passed: bool
    strict: bool
    findings: list[Finding]
    coverage: dict | None = None

    def to_dict(self) -> dict:
        """The verification report as JSON-ready data: what write_report writes and render_summary reads."""
        return {
            "task_id": self.task_id,
            "head_commit": self.head_commit,
            "passed": self.passed,
            "strict": self.strict,
            "coverage": self.coverage,
            "findings": [asdict(f) for f in self.findings],
        }
