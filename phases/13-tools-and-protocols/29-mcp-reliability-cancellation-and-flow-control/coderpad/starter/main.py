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
        raise NotImplementedError("TODO 1: Buffer.push; see PROMPT.md")

    def drain(self):
        raise NotImplementedError("TODO 2: Buffer.drain; see PROMPT.md")

def retry(side_effect, key):
    raise NotImplementedError("TODO 3: retry; see PROMPT.md")

class Race:

    def __init__(self):
        self.state = 'running'
        self.value = None

    def cancel(self):
        raise NotImplementedError("TODO 4: Race.cancel; see PROMPT.md")

    def complete(self, value):
        raise NotImplementedError("TODO 5: Race.complete; see PROMPT.md")
