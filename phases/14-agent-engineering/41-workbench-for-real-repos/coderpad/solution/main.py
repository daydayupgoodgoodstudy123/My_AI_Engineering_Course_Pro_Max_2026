"""Original interview practice for 14-agent-engineering/41-workbench-for-real-repos.

Local source: phases/14-agent-engineering/41-workbench-for-real-repos/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import hashlib

def manifest(files):
    if any((p.startswith('/') or '..' in p.split('/') for p in files)):
        raise ValueError('path')
    return {p: hashlib.sha256(files[p].encode()).hexdigest() for p in sorted(files)}

def git_plan(changes):
    result = {s: [] for s in ('added', 'modified', 'deleted')}
    seen = set()
    for c in changes:
        if c['status'] not in result or c['path'] in seen:
            raise ValueError('changes')
        seen.add(c['path'])
        result[c['status']].append(c['path'])
    return {s: sorted(paths) for s, paths in result.items()}
