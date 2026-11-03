"""Original Phase 13 / Lesson 26 CoderPad practice.

Lesson source: 26-skill-permissions-sandboxes-and-trust/docs/en.md (local course snapshot).
The precise exercise contract is defined in coderpad/PROMPT.md.
Python 3.10+, stdlib only, no network or API keys.
"""
from pathlib import Path

def review(action, policy):

    def decision(verdict, rule):
        return {'verdict': verdict, 'rule': rule}
    if action['capability'] not in policy['capabilities']:
        return decision('deny', 'capability')
    root = Path(policy['root']).resolve()
    p = Path(action['path'])
    if p.is_absolute():
        return decision('deny', 'path')
    p = (root / p).resolve()
    if p != root and root not in p.parents:
        return decision('deny', 'path')
    if action['origin'] is not None and action['origin'] not in policy['origins']:
        return decision('deny', 'origin')
    if action['side_effect'] and (not action['approved']):
        return decision('ask', 'approval')
    return decision('allow', 'policy')

def command_allowed(argv, allowlist):
    return isinstance(argv, (list, tuple)) and all((isinstance(x, str) for x in argv)) and (tuple(argv) in allowlist)
