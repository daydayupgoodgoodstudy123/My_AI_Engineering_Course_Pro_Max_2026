"""Original interview practice for 14-agent-engineering/15-crewai-role-based-crews.

Local source: phases/14-agent-engineering/15-crewai-role-based-crews/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def route_task(routes, query_tokens, role):
    if len({r['name'] for r in routes}) != len(routes):
        raise ValueError('duplicate route')
    scores = [(len(set(r['keywords']) & set(query_tokens)), r['name']) for r in routes if role in r['roles']]
    best = max((s for s, n in scores), default=0)
    names = [n for s, n in scores if s == best]
    return names[0] if best > 0 and len(names) == 1 else None

def validate_handoff(bundle):
    issues = [k for k in ('objective', 'state', 'next_action') if not isinstance(bundle.get(k), str) or not bundle[k].strip()]
    checks = bundle.get('checks')
    if not isinstance(checks, list) or not checks or any((not isinstance(x, str) or not x.strip() for x in checks)):
        issues.append('checks')
    return sorted(issues)
