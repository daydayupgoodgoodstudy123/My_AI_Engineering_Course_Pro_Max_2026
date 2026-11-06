"""What a pipeline run reads and leaves behind.

The scope contract (lesson 36) goes in; feedback records (lesson 37), the diff, the handoff
packet (lesson 40) and the reviewer's report (lesson 39) come out.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

PIPELINES = ("prompt-only", "workbench-guided")


@dataclass(frozen=True)
class Contract:
    """A task's scope contract: the files it may change and the tests that prove it.

    acceptance holds pytest selectors: a node id, a test function, a class, a test module or a
    directory, written the way pytest prints node ids (see realrepo.nodeids).
    """

    allowed: tuple[str, ...]
    forbidden: tuple[str, ...]
    acceptance: tuple[str, ...]


@dataclass(frozen=True)
class FeedbackRecord:
    """One line of feedback_record.jsonl (lesson 37), with the results of a test command.

    command is the exact argv. exit_code is None when the runner failed before the command
    exited; error then says why. results maps every pytest node id the command ran to "passed",
    "failed" or "skipped", and is empty for a command that runs no tests.
    """

    command: tuple[str, ...]
    exit_code: int | None
    results: dict[str, str]
    duration_ms: int = 0
    error: str | None = None


@dataclass(frozen=True)
class RunArtifacts:
    """What one pipeline run left behind, before anything is measured.

    touched: the repo-relative paths the run's diff changes.
    feedback: the run's feedback records, in the order the commands ran.
    claims: what the agent said when it stopped, e.g. {"done": True, "tests_passed": True}.
    handoff: the handoff packet, or None when the run wrote none.
    review: the reviewer's report, {"scores": {dimension: 0 to 2}, "total": ..., "verdict": ...}.
    """

    pipeline: str
    touched: tuple[str, ...]
    feedback: tuple[FeedbackRecord, ...]
    claims: dict
    handoff: dict | None
    review: dict


def load_feedback(text: str) -> tuple[FeedbackRecord, ...]:
    """Parse feedback_record.jsonl: one JSON object per line; blank lines are skipped."""
    records = []
    for line in text.splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        records.append(
            FeedbackRecord(
                command=tuple(raw["command"]),
                exit_code=raw["exit_code"],
                results=dict(raw.get("results") or {}),
                duration_ms=raw.get("duration_ms", 0),
                error=raw.get("error"),
            )
        )
    return tuple(records)
