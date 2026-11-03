"""Original Phase 13 / Lesson 11 CoderPad practice.

Lesson source: 11-mcp-sampling/docs/en.md (local course snapshot).
The precise exercise contract is defined in coderpad/PROMPT.md.
Python 3.10+, stdlib only, no network or API keys.
"""
import base64
import hashlib
import hmac
import json

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()

def seal(state, secret):
    raise NotImplementedError("TODO 1: seal; see PROMPT.md")

def verify(token, secret, principal, method, arguments, now):
    raise NotImplementedError("TODO 2: verify; see PROMPT.md")

def next_round(current, maximum):
    raise NotImplementedError("TODO 3: next_round; see PROMPT.md")
