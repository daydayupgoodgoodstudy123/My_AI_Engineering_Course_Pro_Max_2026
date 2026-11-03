"""Original Phase 13 / Lesson 22 CoderPad practice.

Lesson source: 22-skills-and-agent-sdks/docs/en.md (local course snapshot).
The precise exercise contract is defined in coderpad/PROMPT.md.
Python 3.10+, stdlib only, no network or API keys.
"""
import re

def parse(text):
    lines = text.splitlines()
    if not lines or lines[0] != '---':
        raise ValueError('frontmatter')
    try:
        end = lines.index('---', 1)
    except ValueError:
        raise ValueError('closing delimiter')
    fields = {}
    for line in lines[1:end]:
        if ':' not in line:
            raise ValueError('field')
        key, value = (x.strip() for x in line.split(':', 1))
        if key in fields:
            raise ValueError('duplicate')
        fields[key] = value
    if set(fields) != {'name', 'description'}:
        raise ValueError('fields')
    name = fields['name']
    if len(name) > 64 or re.fullmatch('[a-z][a-z0-9]*(?:-[a-z0-9]+)*', name) is None or (not 1 <= len(fields['description']) <= 1024):
        raise ValueError('metadata')
    body = '\n'.join(lines[end + 1:]).strip()
    if not body:
        raise ValueError('body')
    return dict(fields, body=body)

def validate_bundle(directory_name, text):
    data = parse(text)
    if data['name'] != directory_name:
        raise ValueError('directory')
    return data

def classify(need):
    return {'reusable workflow': 'skill', 'external action': 'tool', 'always-on repository rules': 'instructions', 'event callback': 'hook'}.get(need, 'ordinary code')
