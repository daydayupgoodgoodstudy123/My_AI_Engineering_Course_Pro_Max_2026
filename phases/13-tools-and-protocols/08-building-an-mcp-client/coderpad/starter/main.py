"""Original Phase 13 / Lesson 08 CoderPad practice.

Lesson source: 08-building-an-mcp-client/docs/en.md (local course snapshot).
The precise exercise contract is defined in coderpad/PROMPT.md.
Python 3.10+, stdlib only, no network or API keys.
"""
from copy import deepcopy

class Client:

    def __init__(self, peers):
        self.peers = peers
        self.catalog = {}

    def discover(self):
        raise NotImplementedError("TODO 1: Client.discover; see PROMPT.md")

    def call(self, public_name, args):
        raise NotImplementedError("TODO 2: Client.call; see PROMPT.md")

    def descriptor(self, public_name):
        raise NotImplementedError("TODO 3: Client.descriptor; see PROMPT.md")
