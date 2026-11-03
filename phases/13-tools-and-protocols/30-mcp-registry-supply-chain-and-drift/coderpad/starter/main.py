"""Original Phase 13 / Lesson 30 CoderPad practice.

Lesson source: 30-mcp-registry-supply-chain-and-drift/docs/en.md (local course snapshot).
The precise exercise contract is defined in coderpad/PROMPT.md.
Python 3.10+, stdlib only, no network or API keys.
"""
import re
from copy import deepcopy

class Registry:

    def __init__(self, namespace):
        self.namespace = namespace
        self.admitted = {}
        self.active = None
        self.history = []

    def admit(self, version, record, evidence):
        raise NotImplementedError("TODO 1: Registry.admit; see PROMPT.md")

    def observe(self, live_digest, status):
        raise NotImplementedError("TODO 2: Registry.observe; see PROMPT.md")

    def rollback(self, version):
        raise NotImplementedError("TODO 3: Registry.rollback; see PROMPT.md")
