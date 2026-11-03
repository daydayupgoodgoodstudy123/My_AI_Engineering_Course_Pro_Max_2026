"""Original Phase 13 / Lesson 10 CoderPad practice.

Lesson source: 10-mcp-resources-and-prompts/docs/en.md (local course snapshot).
The precise exercise contract is defined in coderpad/PROMPT.md.
Python 3.10+, stdlib only, no network or API keys.
"""
from copy import deepcopy

class Cache:

    def __init__(self):
        self.items = {}

    def put(self, principal, uri, value, now, ttl):
        raise NotImplementedError("TODO 1: Cache.put; see PROMPT.md")

    def get(self, principal, uri, now):
        raise NotImplementedError("TODO 2: Cache.get; see PROMPT.md")

def render(name, args):
    raise NotImplementedError("TODO 3: render; see PROMPT.md")

def resource_kind(uri):
    raise NotImplementedError("TODO 4: resource_kind; see PROMPT.md")
