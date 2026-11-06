"""Original interview practice for 15-autonomous-systems/15-propose-then-commit.

Local source: phases/15-autonomous-systems/15-propose-then-commit/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def evidence_gate(evidence, required):
    failed = sorted((k for k in set(required) if evidence.get(k) is not True))
    return {'ready': not failed, 'failed': failed}

def git_plan(changes):
    result = {s: [] for s in ('added', 'modified', 'deleted')}
    seen = set()
    for c in changes:
        if c['status'] not in result or c['path'] in seen:
            raise ValueError('changes')
        seen.add(c['path'])
        result[c['status']].append(c['path'])
    return {s: sorted(paths) for s, paths in result.items()}
