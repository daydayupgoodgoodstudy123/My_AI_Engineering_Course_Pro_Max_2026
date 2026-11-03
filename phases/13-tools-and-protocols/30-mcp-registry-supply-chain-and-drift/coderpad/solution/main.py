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
        valid = isinstance(record.get('name'), str) and record['name'].startswith(self.namespace + '.') and (len(record['name']) > len(self.namespace) + 1) and (record.get('status') == 'active') and (evidence.get('namespace') == self.namespace)
        for field, source in (('source_digest', 'source_digest'), ('tools_digest', 'live_digest')):
            d = record.get(field)
            valid = valid and isinstance(d, str) and (re.fullmatch('[0-9a-f]{64}', d) is not None) and (d == evidence.get(source))
        if not valid or version in self.admitted:
            raise ValueError('admission')
        self.admitted[version] = deepcopy(record)
        self.active = version
        self.history.append(('admit', version))
        return version

    def observe(self, live_digest, status):
        if self.active is None:
            return False
        if status != 'active' or live_digest != self.admitted[self.active]['tools_digest']:
            self.history.append(('quarantine', self.active))
            self.active = None
            return False
        return True

    def rollback(self, version):
        if version not in self.admitted:
            raise KeyError(version)
        self.active = version
        self.history.append(('rollback', version))
