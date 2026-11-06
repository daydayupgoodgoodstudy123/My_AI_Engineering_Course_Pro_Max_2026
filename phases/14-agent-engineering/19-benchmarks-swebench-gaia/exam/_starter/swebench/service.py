"""Glue used by the CI job: grade a candidate, store its record, report the run."""
from __future__ import annotations

from .harness import Task, run_task
from .report import report
from .store import ResultStore, TaskRecord
from .stream import AgentRun


class BenchmarkRun:
    def __init__(self, store: ResultStore, tasks: list[Task], verified: set[str]) -> None:
        self.store = store
        self.tasks = {task.instance_id: task for task in tasks}
        self.verified = verified

    def submit(self, instance_id: str, run: AgentRun, wall_ms: int) -> TaskRecord:
        """Grade the agent's patch for one task and store the result."""
        result = run_task(self.tasks[instance_id], run.patch)
        record = TaskRecord(
            result.instance_id, result.status, run.patch.diff, run.tokens, wall_ms, run.steps, result.outcomes
        )
        self.store.add(record)
        return record

    def report(self) -> dict:
        """The run so far, in the all / verified / plus views."""
        issues = {instance_id: task.issue for instance_id, task in self.tasks.items()}
        return report(self.store.records(), issues, self.verified)
