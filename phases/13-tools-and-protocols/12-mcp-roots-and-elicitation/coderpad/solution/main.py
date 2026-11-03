"""Original Phase 13 / Lesson 12 CoderPad practice.

Lesson source: 12-mcp-roots-and-elicitation/docs/en.md (local course snapshot).
The precise exercise contract is defined in coderpad/PROMPT.md.
Python 3.10+, stdlib only, no network or API keys.
"""
from pathlib import Path

def within(root, candidate):
    try:
        r = Path(root).resolve()
        p = Path(candidate)
        p = (r / p).resolve() if not p.is_absolute() else p.resolve()
        return p == r or r in p.parents
    except (OSError, RuntimeError):
        return False

def confirm(action, token, used):
    if action not in ('accept', 'decline', 'cancel') or token in used:
        raise ValueError('confirmation')
    used.add(token)
    return {'status': {'accept': 'confirmed', 'decline': 'declined', 'cancel': 'canceled'}[action], 'execute': action == 'accept'}

def validate_form(data):
    if not isinstance(data, dict) or set(data) != {'title'} or (not isinstance(data['title'], str)) or (not 1 <= len(data['title'].strip()) <= 40):
        raise ValueError('form')
    return {'title': data['title'].strip()}
