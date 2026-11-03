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
        if ttl < 0:
            raise ValueError('ttl')
        self.items[principal, uri] = (now + ttl, deepcopy(value))

    def get(self, principal, uri, now):
        item = self.items.get((principal, uri))
        return deepcopy(item[1]) if item is not None and now < item[0] else None

def render(name, args):
    if name != 'summarize':
        raise KeyError(name)
    if not isinstance(args, dict) or set(args) != {'text'} or (not isinstance(args['text'], str)) or (not args['text'].strip()):
        raise ValueError('args')
    return [{'role': 'user', 'content': 'Summarize: ' + args['text'].strip()}]

def resource_kind(uri):
    for prefix, kind in (('notes://', 'resource'), ('ui://', 'ui')):
        if isinstance(uri, str) and uri.startswith(prefix) and (len(uri) > len(prefix)):
            return kind
    raise ValueError('uri')
