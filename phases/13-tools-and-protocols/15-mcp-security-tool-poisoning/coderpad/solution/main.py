"""Original Phase 13 / Lesson 15 CoderPad practice.

Lesson source: 15-mcp-security-tool-poisoning/docs/en.md (local course snapshot).
The precise exercise contract is defined in coderpad/PROMPT.md.
Python 3.10+, stdlib only, no network or API keys.
"""
import hashlib, json
from collections import Counter

def fingerprint(tool):
    return hashlib.sha256(json.dumps(tool, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()

def scan(catalog, approved):
    entries = [(p + '::' + t['name'], t) for p, tools in catalog.items() for t in tools]
    counts = Counter((n for n, t in entries))
    findings = set()
    for name, t in entries:
        if name not in approved:
            findings.add((name, 'unapproved'))
        elif fingerprint(t) != approved[name]:
            findings.add((name, 'drift'))
        if any((x in t['description'].casefold() for x in ('ignore previous', 'send secrets', 'override policy'))):
            findings.add((name, 'poisoning'))
        if counts[name] > 1:
            findings.add((name, 'collision'))
    return sorted(findings)

def admitted(catalog, approved):
    blocked = {name for name, code in scan(catalog, approved)}
    return sorted({p + '::' + t['name'] for p, tools in catalog.items() for t in tools} - blocked)
