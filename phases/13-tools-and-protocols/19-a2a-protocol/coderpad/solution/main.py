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
        content = (target, artifact)
        if message_id in self.seen:
            if self.seen[message_id] != content:
                raise ValueError('conflicting replay')
            return self.status
        allowed = {'submitted': {'working', 'rejected'}, 'working': {'input-required', 'completed', 'failed', 'canceled'}, 'input-required': {'working', 'canceled'}}
        if target not in allowed.get(self.status, set()):
            raise ValueError('transition')
        if target == 'completed':
            if not isinstance(artifact, str) or not artifact:
                raise ValueError('artifact')
        elif artifact is not None:
            raise ValueError('artifact')
        self.status = target
        self.seen[message_id] = content
        if artifact is not None:
            self.artifacts.append(artifact)
        return self.status

def text_parts(parts):
    return '\n'.join((p['text'] for p in parts if p['type'] == 'text'))
