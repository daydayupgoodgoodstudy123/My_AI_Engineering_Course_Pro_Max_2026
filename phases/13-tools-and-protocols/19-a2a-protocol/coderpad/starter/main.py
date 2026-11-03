"""Original Phase 13 / Lesson 19 CoderPad practice.

Lesson source: 19-a2a-protocol/docs/en.md (local course snapshot).
The precise exercise contract is defined in coderpad/PROMPT.md.
Python 3.10+, stdlib only, no network or API keys.
"""
class Task:

    def __init__(self):
        self.status = 'submitted'
        self.seen = {}
        self.artifacts = []

    def apply(self, message_id, target, artifact=None):
        raise NotImplementedError("TODO 1: Task.apply; see PROMPT.md")

def text_parts(parts):
    raise NotImplementedError("TODO 2: text_parts; see PROMPT.md")
