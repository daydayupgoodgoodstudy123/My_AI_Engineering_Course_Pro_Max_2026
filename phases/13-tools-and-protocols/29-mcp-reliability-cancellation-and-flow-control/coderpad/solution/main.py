"""Original Phase 13 / Lesson 29 CoderPad practice.

Lesson source: 29-mcp-reliability-cancellation-and-flow-control/docs/en.md (local course snapshot).
The precise exercise contract is defined in coderpad/PROMPT.md.
Python 3.10+, stdlib only, no network or API keys.
"""
class Buffer:

    def __init__(self, capacity):
        if type(capacity) is not int or capacity <= 0:
            raise ValueError('capacity')
        self.capacity = capacity
        self.items = []

    def push(self, kind, value):
        if kind not in ('progress', 'final'):
            raise ValueError('kind')
        if len(self.items) == self.capacity:
            index = next((i for i, x in enumerate(self.items) if x['kind'] == 'progress'), None)
            if index is None:
                if kind == 'final':
                    raise BufferError('final queue full')
                return False
            self.items.pop(index)
        self.items.append({'kind': kind, 'value': value})
        return True

    def drain(self):
        result = self.items
        self.items = []
        return result

def retry(side_effect, key):
    return 'safe' if not side_effect else 'deduplicated' if isinstance(key, str) and key else 'unsafe'

class Race:

    def __init__(self):
        self.state = 'running'
        self.value = None

    def cancel(self):
        if self.state != 'running':
            return False
        self.state = 'canceled'
        return True

    def complete(self, value):
        if self.state != 'running':
            return False
        self.state = 'completed'
        self.value = value
        return True
