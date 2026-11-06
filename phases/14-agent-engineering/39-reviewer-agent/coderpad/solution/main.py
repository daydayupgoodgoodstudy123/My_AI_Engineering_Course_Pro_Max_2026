"""Original interview practice for 14-agent-engineering/39-reviewer-agent.

Local source: phases/14-agent-engineering/39-reviewer-agent/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def unsupported_claims(claims, evidence_ids):
    if len({c['id'] for c in claims}) != len(claims):
        raise ValueError('duplicate claim')
    known = set(evidence_ids)
    return sorted((c['id'] for c in claims if not c['references'] or not set(c['references']) <= known))

def git_plan(changes):
    result = {s: [] for s in ('added', 'modified', 'deleted')}
    seen = set()
    for c in changes:
        if c['status'] not in result or c['path'] in seen:
            raise ValueError('changes')
        seen.add(c['path'])
        result[c['status']].append(c['path'])
    return {s: sorted(paths) for s, paths in result.items()}
