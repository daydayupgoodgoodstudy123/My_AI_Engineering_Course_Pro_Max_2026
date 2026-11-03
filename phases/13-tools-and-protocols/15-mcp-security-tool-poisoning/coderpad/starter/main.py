"""Original Phase 13 / Lesson 15 CoderPad practice.

Lesson source: 15-mcp-security-tool-poisoning/docs/en.md (local course snapshot).
The precise exercise contract is defined in coderpad/PROMPT.md.
Python 3.10+, stdlib only, no network or API keys.
"""
import hashlib, json
from collections import Counter

def fingerprint(tool):
    raise NotImplementedError("TODO 1: fingerprint; see PROMPT.md")

def scan(catalog, approved):
    raise NotImplementedError("TODO 2: scan; see PROMPT.md")

def admitted(catalog, approved):
    raise NotImplementedError("TODO 3: admitted; see PROMPT.md")
