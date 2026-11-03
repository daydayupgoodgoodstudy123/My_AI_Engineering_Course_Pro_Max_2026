"""Original Phase 13 / Lesson 05 CoderPad practice.

Lesson source: 05-tool-schema-design/docs/en.md (local course snapshot).
The precise exercise contract is defined in coderpad/PROMPT.md.
Python 3.10+, stdlib only, no network or API keys.
"""
import re
from collections import Counter

def lint(tool):
    codes = []
    name = tool.get('name')
    if not isinstance(name, str) or re.fullmatch('[a-z][a-z0-9_]{0,39}', name) is None:
        codes.append('name')
    desc = tool.get('description')
    if not isinstance(desc, str) or not 1 <= len(desc) <= 1024 or 'Use when' not in desc or ('Do not use' not in desc):
        codes.append('description')
    s = tool.get('input_schema')
    valid = isinstance(s, dict) and s.get('type') == 'object' and isinstance(s.get('properties'), dict) and isinstance(s.get('required'), list) and all((isinstance(x, str) for x in s['required']))
    if valid:
        valid = len(set(s['required'])) == len(s['required']) and set(s['required']) <= set(s['properties']) and (s.get('additionalProperties') is False)
    if not valid:
        codes.append('schema')
    return sorted(codes)

def lint_registry(tools):
    counts = Counter((t.get('name') for t in tools if isinstance(t.get('name'), str)))
    return {'findings': [{'index': i, 'codes': codes} for i, t in enumerate(tools) if (codes := lint(t))], 'duplicates': sorted((n for n, c in counts.items() if c > 1))}

def clean_names(tools):
    duplicates = set(lint_registry(tools)['duplicates'])
    return sorted({t['name'] for t in tools if not lint(t) and t['name'] not in duplicates})
