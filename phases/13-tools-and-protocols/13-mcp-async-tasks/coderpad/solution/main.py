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
        if task_id in self.tasks:
            raise ValueError('duplicate')
        self.tasks[task_id] = {'id': task_id, 'owner': owner, 'status': 'queued'}
        self._persist()
        return self.get(task_id)

    def transition(self, task_id, owner, status):
        if task_id not in self.tasks or self.tasks[task_id]['owner'] != owner:
            raise KeyError(task_id)
        allowed = {'queued': {'working', 'canceled'}, 'working': {'completed', 'failed', 'canceled'}}
        if status not in allowed.get(self.tasks[task_id]['status'], set()):
            raise ValueError('transition')
        self.tasks[task_id]['status'] = status
        self._persist()
        return self.get(task_id)

    def purge_terminal(self):
        ids = sorted((k for k, v in self.tasks.items() if v['status'] in ('completed', 'failed', 'canceled')))
        for k in ids:
            del self.tasks[k]
        self._persist()
        return ids
