"""Original Phase 13 / Lesson 13 CoderPad practice.

Lesson source: 13-mcp-async-tasks/docs/en.md (local course snapshot).
The precise exercise contract is defined in coderpad/PROMPT.md.
Python 3.10+, stdlib only, no network or API keys.
"""
import json
from pathlib import Path

class TaskStore:

    def __init__(self, path):
        self.path = Path(path)
        self.tasks = json.loads(self.path.read_text()) if self.path.exists() else {}

    def _persist(self):
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.tasks, sort_keys=True))
        temporary.replace(self.path)

    def get(self, task_id):
        return self.tasks[task_id].copy()

    def create(self, task_id, owner):
        raise NotImplementedError("TODO 1: TaskStore.create; see PROMPT.md")

    def transition(self, task_id, owner, status):
        raise NotImplementedError("TODO 2: TaskStore.transition; see PROMPT.md")

    def purge_terminal(self):
        raise NotImplementedError("TODO 3: TaskStore.purge_terminal; see PROMPT.md")
